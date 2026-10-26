# Progress / save point

Last updated **2026-10-26**. Read this first when picking the project back up.

## Where we are

Steps 1-4 of the CLAUDE.md build order are **done and pushed**. The CLI works
end to end against the live model and answers all three of the worked examples
from the build order correctly. **Step 5 (the 20-question test set) has not
been started.**

| Step | State |
|---|---|
| 1 Project setup | done |
| 2 Game data + load_data.py | done |
| 3 Lookup tools + tests | done |
| 4 Ollama agent + CLI | done, not yet scored |
| 5 Test set of 20 + scorer | **not started** |

`pytest` is green at **49 tests**. Nothing is half-finished or uncommitted.

## Verified working

Run live against `qwen2.5:7b` on 2026-10-26, all three correct:

| Question | Answer |
|---|---|
| Does Enigma's Black Hole go through BKB? | yes, from the dump |
| Does Euls dispel Ice Path stun? | no -- basic dispel vs a strong requirement, derived in code |
| Can Lotus Orb reflect Doom? | refuses -- reflection is not in the data |

The third one is the important one: it declined rather than inventing an answer.

## Decisions made (so they do not get re-litigated)

- **Data lives in the repo.** `data/` is committed (2.8 MB) so the repo pins
  the patch the answers were verified against. Refresh procedure in
  `data/SOURCE.md`.
- **Plain dicts, not pydantic models.** The upstream data is too irregular to
  model without guessing which fields are optional.
- **Provenance is a commit and date, never a patch number.** The dumps carry
  no patch stamp, and `patch.json`'s newest entry (7.41, 2026-03-24) is seven
  months older than the commit we pulled. Saying "patch 7.41" would be false.
- **Ambiguous names return every candidate.** "Shadowraze" is three abilities,
  "Hex" belongs to two heroes. The agent lists them instead of picking.
- **No tool call means no answer.** One reminder, one retry, then refuse.
- **A curated overrides file is allowed**, but every value is tagged
  `source: curated` and the agent must say so out loud.
- **Model: `qwen2.5:7b`**, with `qwen3` as the fallback if tool calling proves
  unreliable. So far it has called tools correctly every time.

## What is left

### Step 5, the actual next task
1. Draft `tests/interactions.json` -- 20 interaction questions with expected
   answers. **Review these before locking them in.**
2. A script that runs all 20 against the live model and scores it.
3. Log every failure. Failures tell us whether the gap is the data, the tools,
   or the model mishandling tool calls -- which decides whether the fix is a
   prompt change, more curation, or `qwen3`.
4. Target from the CLAUDE.md "done when" list: **>= 14/20**.

### Open item needing a human
**The 16 curated override values in `src/tools/overrides.json` have not been
reviewed.** They were entered from model memory and are flagged
`PENDING HUMAN REVIEW`. The five low-confidence ones most likely to be wrong:

| Ability | Hero | Value | Why unsure |
|---|---|---|---|
| Terror Wave | Terrorblade | no | newer ability |
| Toss | Tiny | partial | displacement vs damage split |
| Stifling Dagger | Phantom Assassin | partial | physical lands, slow may not |
| Stinger | Sand King | partial | unsure of current damage type |
| Counterspell | Anti-Mage | n/a | question may be ill-formed |

Correcting these is a JSON edit and would likely move the Step 5 score.

### Known limitations, by design
- **Spell reflection is not modelled at all** (Lotus Orb, Linken's). No field
  or text in the dumps says which spells are reflectable. The agent refuses
  these rather than guessing.
- **`dispellable` is missing on 333 abilities and `dmg_type` on 377.** Too
  many to curate. These return `unknown`.
- Item dispel strength is parsed out of free text (`"Dispel Type: Basic
  Dispel"`), which only 15 items declare. Fragile by nature.
- First question of a session takes ~40 s while Ollama loads 4.7 GB; later
  ones are much faster. Relevant to the latency goal in the design principles.

### Backlog -- explicitly not started
Combat log parsing, live Game State Integration, a router model, voice, and
fine-tuning. Per the CLAUDE.md backlog section, do not start these.

## Friction worth fixing

The Claude Code session was running in a git worktree of an unrelated repo
(`worldpulse-news-app`), which blocked the file-writing tool for every path in
this project and forced shell workarounds. **Start the next session rooted in
`D:\Python Projects\dota-gpt`.**

## Picking back up

```bash
cd "D:\Python Projects\dota-gpt"
.venv\Scripts\python -m pytest -q
ollama list
.venv\Scripts\python -m src.agent.cli --show-tools "Does Black Hole go through BKB?"
```

If all three behave, nothing has rotted and Step 5 can start.
