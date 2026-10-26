# Data provenance

All JSON in this directory is copied unmodified from the `build/` folder of
[odota/dotaconstants](https://github.com/odota/dotaconstants).

| | |
|---|---|
| Source commit | `5c0242df9057848fa2036ca3fafe9f2bd4508163` |
| Commit date | 2026-10-11T18:45:43-07:00 |
| Pulled on | 2026-10-26T00:17:26Z |
| Files | heroes.json, abilities.json, hero_abilities.json, items.json, patch.json |

## Patch version — read this before trusting any patch claim

The newest entry in `patch.json` is **7.41, dated 2026-03-24**, but the commit
above is from **2026-10-11**. The data therefore reflects the game as of roughly
October 2026, while `patch.json` only enumerates patches up to 7.41.

`patch.json` is a list of patch names and release dates. It does **not** state
which patch the sibling files were generated from. So:

- The honest provenance is the **commit SHA and date** above.
- "Latest entry in patch.json" is a **lower bound**, not the actual patch.

Do not print a patch number that is not derived from one of those two facts.

## Refreshing

```bash
git clone --depth 1 https://github.com/odota/dotaconstants.git
cp dotaconstants/build/{heroes,abilities,hero_abilities,items,patch}.json data/
```
Then update the table above.
