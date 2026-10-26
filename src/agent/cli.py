"""Question in, answer out.

    python -m src.agent.cli                      interactive
    python -m src.agent.cli "Does BH pierce BKB?" one-shot
    python -m src.agent.cli --show-tools ...      print the raw tool results

--show-tools is the audit switch: it proves an answer came from the data
rather than from the model, which is the whole claim of this project.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..load_data import source_commit
from .client import DEFAULT_MODEL, ask


def _render(result: dict, show_tools: bool) -> None:
    if show_tools:
        if not result["trace"]:
            print("  [no tools were called]")
        for step in result["trace"]:
            print(f"  -> {step['tool']}({json.dumps(step['arguments'])})")
            print("     " + json.dumps(step["result"], default=str)[:600])
        print()
    print(result["answer"])
    if result.get("refused"):
        print(f"\n[refused: {result.get('reason')}]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dota-gpt", description=__doc__)
    parser.add_argument("question", nargs="*", help="question to ask")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--show-tools",
        action="store_true",
        help="print every tool call and its raw result",
    )
    args = parser.parse_args(argv)

    provenance = source_commit()
    print(
        f"Dota GPT -- model {args.model}, data from dotaconstants commit "
        f"{provenance['commit']} ({(provenance['commit_date'] or '')[:10]})"
    )

    if args.question:
        result = ask(" ".join(args.question), model=args.model)
        _render(result, args.show_tools)
        return 0

    print("Ask a question, or Ctrl-C to quit.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question.lower() in {"quit", "exit"}:
            return 0
        try:
            result = ask(question, model=args.model)
        except Exception as exc:  # a dead server should not kill the session
            print(f"[error: {exc}]\n")
            continue
        _render(result, args.show_tools)
        print()


if __name__ == "__main__":
    sys.exit(main())
