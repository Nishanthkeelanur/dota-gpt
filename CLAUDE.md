# CLAUDE.md — Dota GPT

Project instructions for Claude Code. Read this fully before doing anything.

---

## 1. What we're building

**Dota GPT** — a Dota 2 assistant that answers spell/mechanic interaction questions
by looking up real game data, not by guessing from model memory.

Long term it also answers live match questions for casters ("how fast did CM die
to PL?"). **That is backlog. Do not build it yet.**

**MVP scope (this is all we are building right now):**

A command-line tool where I type a plain-English question like
"Does Black Hole go through BKB?" and a local LLM answers it by calling Python
functions that read real Dota ability data, and names the patch it used.

---

## 2. How I want you to work with me

This matters more than the code. Follow it strictly.

- **Explain before you do.** Before each step, tell me in plain English: what
  you're about to do, why, and what the result should look like. Then wait for
  me to say go. Do not chain five steps together and hand me a finished folder.
- **One step at a time.** Small commits, small diffs. After each step, tell me
  what changed and how to verify it myself.
- **Teach as you go.** I'm comfortable with Python, ETL and SQL. LLM tooling,
  tool-calling and local model serving are new to me. When you use something
  from that side, explain the concept briefly before the code.
- **Ask, don't assume.** If a design decision could reasonably go two ways,
  ask me which I want instead of picking silently.
- **No silent installs.** Tell me what you're installing and why, before you
  install it.
- **Say when you're unsure.** Especially on Dota mechanics. If the data doesn't
  answer something, say so rather than filling the gap from memory.
- **Don't refactor what I didn't ask about.** Stay in scope.

---

## 3. Tech stack

- Python 3.11+, virtual environment in the repo
- Data: JSON files for now (Postgres only if we outgrow it — ask me first)
- Local model: **Ollama** running `qwen2.5:7b`
- Deps: `requests`, `ollama`, `pydantic`, `pytest`
- Tests: `pytest`

---

## 4. Repo layout

```
dota-gpt/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── data/              # dotaconstants JSON dumps
├── src/
│   ├── load_data.py   # loads + normalises the JSON
│   ├── tools/         # the lookup functions the LLM can call
│   └── agent/         # Ollama client, tool registration, CLI loop
└── tests/
    ├── interactions.json   # my 20 known-answer questions
    └── test_tools.py
```

---

## 5. Build order

Work through these in order. Stop and check in with me after each one.

### Step 1 — Project setup
Repo, venv, `requirements.txt`, folder skeleton, `.gitignore`, stub README.

### Step 2 — Get the game data
Pull the `build/` folder from the **odota/dotaconstants** GitHub repo.
Key files: `heroes.json`, `abilities.json`, `hero_abilities.json`, `items.json`,
`patch.json`.

Then write `src/load_data.py` and **show me** a sample hero with its abilities,
plus which fields actually exist — specifically: damage type, pierces spell
immunity, dispellable, cooldown, mana cost, behaviour. I need to know what the
data does and doesn't cover before we build on it.

### Step 3 — Lookup tools (`src/tools/`)
Plain Python functions, each unit-tested:

- `get_hero(name)` → stats + ability list
- `get_ability(name)` → full ability data
- `pierces_spell_immunity(ability)` → yes/no + notes
- `is_dispellable(ability)` → basic / strong / none
- `compare_abilities(a, b)` → side-by-side for interaction questions

Must handle aliases — "BKB" = Black King Bar, "PL" = Phantom Lancer. A simple
alias map is fine.

### Step 4 — Wire up the LLM (`src/agent/`)
- `ollama pull qwen2.5:7b`
- Register the Step 3 functions as tools via Ollama's tool calling
- System prompt rules: answer **only** from tool results; if the data doesn't
  cover it, say "not sure"; always state the patch version
- A simple CLI loop: question in, answer out

Explain how tool calling works before you write this part.

### Step 5 — Test set
- `tests/interactions.json` — 20 interaction questions with expected answers.
  Draft them, but let me review before we lock them in. Examples:
  - Does Enigma's Black Hole go through BKB?
  - Can Lotus Orb reflect Doom?
  - Does Eul's dispel Ice Path stun?
- A script that runs all 20 and scores it
- Log every failure — failures tell us which data or tools are missing

---

## 6. Done when

- [ ] CLI answers basic interaction questions end to end
- [ ] Scores ≥ 14/20 on the test set
- [ ] `pytest` passes
- [ ] Pushed to GitHub with a README that explains setup and usage

---

## 7. Backlog — do NOT start these

- Combat log parsing from replays (hits, damage per hit, time to kill)
- Live data via Valve's Game State Integration
- Router/orchestrator model in front of the specialist tools
- Voice input/output
- Fine-tuning on interaction Q&A

---

## 8. Design principles to hold onto

- **The model never answers mechanics from memory.** Dota patches constantly.
  Every factual answer comes from a tool result.
- **Code does the maths, not the LLM.** The LLM parses the question and
  phrases the answer. Nothing else.
- **Latency matters** (casters, later). Keep the path short.
