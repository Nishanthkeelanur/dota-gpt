"""The tool-calling loop.

The model never executes anything. It emits an intent -- a function name and
arguments -- and this module decides whether to run it, runs it, and feeds the
result back. The factual content of every answer therefore comes out of the
JSON dumps via src/tools, not out of the model weights.

The loop is injectable: pass chat_fn to drive it with a scripted fake model,
so the tests cover the control flow without needing Ollama running.
"""

from __future__ import annotations

import json

from .prompt import NOT_SURE, RETRY_REMINDER, SYSTEM_PROMPT, is_meta
from .tools_spec import TOOL_SCHEMAS, execute

DEFAULT_MODEL = "qwen2.5:7b"
MAX_ITERATIONS = 6


def _get(obj, key, default=None):
    """Read a field from either a dict or an object with attributes.

    The Ollama client returns typed objects (ToolCall, Function); the fake
    model in the tests returns plain dicts. Both must work.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _ollama_chat(model: str, messages: list, tools: list):
    from ollama import chat

    return chat(model=model, messages=messages, tools=tools)


def ask(
    question: str,
    model: str = DEFAULT_MODEL,
    chat_fn=None,
    max_iterations: int = MAX_ITERATIONS,
) -> dict:
    """Answer one question. Returns the answer plus an auditable trace."""
    chat_fn = chat_fn or _ollama_chat
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    trace: list[dict] = []
    tools_used = 0
    retried = False

    for _ in range(max_iterations):
        reply = chat_fn(model=model, messages=messages, tools=TOOL_SCHEMAS)
        message = _get(reply, "message", {})
        calls = _get(message, "tool_calls") or []

        if calls:
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": _get(_get(c, "function"), "name"),
                                "arguments": _get(_get(c, "function"), "arguments"),
                            },
                        }
                        for c in calls
                    ],
                }
            )
            for call in calls:
                fn = _get(call, "function")
                name = _get(fn, "name")
                args = _get(fn, "arguments") or {}
                result = execute(name, dict(args))
                tools_used += 1
                trace.append({"tool": name, "arguments": dict(args), "result": result})
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(result, default=str),
                    }
                )
            continue

        content = (_get(message, "content") or "").strip()

        # Enforcement: a factual question that produced no tool call gets one
        # reminder and one retry. If it still calls nothing, we refuse rather
        # than hand over an answer from model memory.
        if tools_used == 0 and not is_meta(question):
            if not retried:
                retried = True
                messages.append({"role": "user", "content": RETRY_REMINDER})
                continue
            return {
                "question": question,
                "answer": NOT_SURE,
                "tools_used": 0,
                "trace": trace,
                "refused": True,
                "reason": "model answered without consulting any tool, twice",
            }

        return {
            "question": question,
            "answer": content,
            "tools_used": tools_used,
            "trace": trace,
            "refused": False,
            "retried": retried,
        }

    return {
        "question": question,
        "answer": NOT_SURE,
        "tools_used": tools_used,
        "trace": trace,
        "refused": True,
        "reason": f"no final answer within {max_iterations} iterations",
    }
