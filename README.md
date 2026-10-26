# Dota GPT

A Dota 2 assistant that answers spell and mechanic interaction questions by
looking up real game data, not by guessing from model memory.

```
$ python -m src.agent.cli "Does Enigma's Black Hole go through BKB?"
Dota GPT -- model qwen2.5:7b, data from dotaconstants commit 5c0242df (2026-10-11)

Yes, Enigma's Black Hole goes through BKB as of dotaconstants commit
5c0242df, 2026-10-11.
```

A local LLM parses the question and phrases the answer. Every factual claim
comes from a Python function reading the real ability data, and the answer
names the data it used.

## Why it works this way

Dota patches constantly and LLMs are confidently wrong about mechanics. So the
model is never allowed to answer from its own knowledge:

- **Facts come from tools, not weights.** The model emits a function name and
  arguments; the code runs the lookup and hands back the result.
- **Code does the maths.** Dispel-strength verdicts are computed in Python.
  The model only phrases them.
- **Absence means "not sure", never "no".** The upstream data annotates
  spell immunity on only 65% of hero abilities, so a missing field returns
  `unknown` and the assistant says it does not know.
- **If it skips a tool, the answer is thrown away.** One reminder, one retry,
  then it refuses rather than answer from memory.

## Setup

Requires Python 3.11+ and [Ollama](https://ollama.com).

```bash
git clone https://github.com/Nishanthkeelanur/dota-gpt.git
cd dota-gpt

py -3.12 -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
ollama pull qwen2.5:7b        # ~4.7 GB, once
```

The game data is committed to `data/`, so there is nothing else to fetch.

## Usage

```bash
python -m src.agent.cli                                  # interactive
python -m src.agent.cli "Does Euls dispel Ice Path?"     # one-shot
python -m src.agent.cli --show-tools "Does BH pierce?"   # audit the lookups
python -m src.agent.cli --model qwen3 "..."              # different model
```

`--show-tools` prints every tool call and its raw result. That is the switch
that proves an answer came from the data rather than the model.

## Tests

```bash
pytest
```

49 tests. The agent loop is tested against a scripted fake model, so the suite
runs in under a second and does not need Ollama.

## Data

`data/` holds five JSON dumps from
[odota/dotaconstants](https://github.com/odota/dotaconstants), pinned to one
commit. See `data/SOURCE.md` for the commit, the refresh procedure, and why
the assistant quotes a commit rather than a patch number.

A field-coverage report:

```bash
python -m src.load_data
```

## Layout

```
data/              five dotaconstants dumps + SOURCE.md provenance
src/load_data.py   loads and normalises the JSON
src/tools/         the lookup functions the LLM may call
  names.py         name resolution and the alias map (BKB, PL, Euls...)
  mechanics.py     the six lookups, each tagging its own provenance
  overrides.json   16 hand-curated values, flagged as such at point of use
src/agent/         Ollama client, tool schemas, system prompt, CLI
tests/             49 tests
```

## Tech

Python 3.12 · Ollama (`qwen2.5:7b`) · pydantic · pytest
