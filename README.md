# Dota GPT

A Dota 2 assistant that answers spell and mechanic interaction questions by
looking up real game data, not by guessing from model memory.

Ask it something like *"Does Black Hole go through BKB?"* and a local LLM answers
by calling Python functions that read actual Dota ability data — and tells you
which patch that data came from.

## Why

Dota patches constantly, and LLMs are confidently wrong about mechanics. So the
model never answers from memory here: every factual claim comes from a tool
result, and the code does the maths rather than the LLM.

## Status

🚧 Early development. Step 1 of 5 — project skeleton only. Nothing works yet.

- [x] Step 1 — Project setup
- [ ] Step 2 — Game data (odota/dotaconstants)
- [ ] Step 3 — Lookup tools
- [ ] Step 4 — Ollama tool-calling agent
- [ ] Step 5 — Known-answer test set

## Setup

> Not usable yet — these steps will work from Step 4 onward.

Requires Python 3.11+ and [Ollama](https://ollama.com).

```bash
git clone https://github.com/Nishanthkeelanur/dota-gpt.git
cd dota-gpt

py -3.12 -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
ollama pull qwen2.5:7b
```

## Usage

_To be written once the CLI exists (Step 4)._

## Tests

```bash
pytest
```

## Tech

Python 3.12 · Ollama (`qwen2.5:7b`) · pydantic · pytest · data from
[odota/dotaconstants](https://github.com/odota/dotaconstants)
