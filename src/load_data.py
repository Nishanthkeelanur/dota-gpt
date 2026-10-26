"""Load and normalise the dotaconstants JSON dumps.

Deliberately returns plain dicts, not typed models. The data is irregular
(see audit output below) and we don't yet know which fields are genuinely
optional, so modelling it would mean guessing. Step 3 can model what it needs.

Run `python -m src.load_data` for a field-coverage report and a sample hero.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FILES = ("heroes", "abilities", "hero_abilities", "items", "patch")

# The six fields CLAUDE.md section 5 asks about, plus targeting.
AUDIT_FIELDS = (
    "dname",
    "desc",
    "behavior",
    "dmg_type",
    "bkbpierce",
    "dispellable",
    "cd",
    "mc",
    "target_team",
    "target_type",
)


def load_json(name: str) -> dict | list:
    """Load one dump by bare name, e.g. load_json("heroes")."""
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing. See data/SOURCE.md for how to fetch the dumps."
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_all() -> dict[str, dict | list]:
    """Load every dump into a dict keyed by bare name."""
    return {name: load_json(name) for name in FILES}


# --- normalisation helpers -------------------------------------------------
#
# Two irregularities bite everywhere, so handle them in one place:
#   1. Scalar-or-list: `behavior` may be "Passive" or ["AOE", "Point Target"].
#   2. Per-level values: `cd` / `mc` are "40" when flat, or ["20","18","16"]
#      when they scale with ability level.
# A third, nastier case: some fields are an EMPTY list where a string is
# expected (e.g. bkbpierce == [] on 7 abilities). Treat that as missing.


def as_list(value) -> list:
    """Coerce scalar-or-list into a list. None and "" become []."""
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, list) else [value]


def is_missing(value) -> bool:
    """True if a field is absent, blank, or the empty-list placeholder."""
    return value is None or value == "" or value == []


def levels(value) -> list[str]:
    """Per-level values as a list of strings. "40" -> ["40"]."""
    return [str(v) for v in as_list(value)]


def value_at_level(value, level: int = 1) -> str | None:
    """Value at a 1-indexed ability level, clamped to what exists."""
    vals = levels(value)
    if not vals:
        return None
    return vals[min(level, len(vals)) - 1]


# --- indexes ---------------------------------------------------------------


def heroes_by_name(heroes: dict) -> dict[str, dict]:
    """Index heroes.json by localised display name, e.g. "Enigma"."""
    return {h["localized_name"]: h for h in heroes.values() if "localized_name" in h}


def real_ability_names(abilities: dict, hero_abilities: dict) -> list[str]:
    """Ability keys actually belonging to a playable hero.

    abilities.json holds ~3100 entries, most of them irrelevant: event
    reskins (greevil_*, cny2015_*), talent rows (special_bonus_*) and
    engine stubs. Only those referenced by hero_abilities.json matter.
    """
    names = {
        a
        for entry in hero_abilities.values()
        for a in entry.get("abilities", [])
        if a in abilities
    }
    return sorted(names)


def hero_key_for(hero_name: str, heroes: dict) -> str | None:
    """Map a display name to its npc_dota_hero_* key."""
    for h in heroes.values():
        if h.get("localized_name", "").lower() == hero_name.lower():
            return h.get("name")
    return None


def abilities_for_hero(hero_name: str, data: dict) -> list[dict]:
    """Full ability dicts for a hero, in in-game order, key included."""
    key = hero_key_for(hero_name, data["heroes"])
    if key is None:
        return []
    entry = data["hero_abilities"].get(key, {})
    out = []
    for a in entry.get("abilities", []):
        ability = data["abilities"].get(a)
        if ability is not None:
            out.append({"key": a, **ability})
    return out


# --- audit -----------------------------------------------------------------


def field_coverage(data: dict) -> list[tuple[str, int, int, float]]:
    """Per-field (name, present, total, percent) across real hero abilities."""
    names = real_ability_names(data["abilities"], data["hero_abilities"])
    rows = []
    for field in AUDIT_FIELDS:
        present = sum(
            1 for n in names if not is_missing(data["abilities"][n].get(field))
        )
        rows.append((field, present, len(names), 100 * present / len(names)))
    return rows


def latest_patch(patch: list) -> dict | None:
    """Newest entry in patch.json. A LOWER BOUND on the real patch -- the
    dumps carry no patch stamp of their own. See data/SOURCE.md."""
    return patch[-1] if patch else None


def _report() -> None:
    data = load_all()
    heroes, abilities = data["heroes"], data["abilities"]
    names = real_ability_names(abilities, data["hero_abilities"])

    print("=" * 72)
    print("DOTA GPT -- data load report")
    print("=" * 72)
    print(f"heroes            : {len(heroes)}")
    print(f"abilities (raw)   : {len(abilities)}")
    print(f"abilities (hero)  : {len(names)}")
    print(f"items             : {len(data['items'])}")
    patch = latest_patch(data["patch"])
    if patch:
        print(f"patch.json newest : {patch['name']} ({patch['date'][:10]}) -- LOWER BOUND")

    print("\nFIELD COVERAGE across the %d real hero abilities" % len(names))
    print(f"{'field':<14}{'present':>9}{'coverage':>10}")
    print("-" * 33)
    for field, present, total, pct in field_coverage(data):
        print(f"{field:<14}{present:>9}{pct:>9.1f}%")

    for field in ("bkbpierce", "dispellable", "dmg_type"):
        counts = Counter(
            "<missing>" if is_missing(abilities[n].get(field)) else str(abilities[n][field])
            for n in names
        )
        print(f"\n{field} values: {dict(counts.most_common())}")

    print("\n" + "=" * 72)
    print("SAMPLE HERO: Enigma")
    print("=" * 72)
    for ability in abilities_for_hero("Enigma", data):
        print(f"\n{ability.get('dname') or ability['key']}  [{ability['key']}]")
        print(f"  behavior    : {', '.join(as_list(ability.get('behavior'))) or '-'}")
        print(f"  dmg_type    : {ability.get('dmg_type') or '<missing>'}")
        print(f"  bkbpierce   : {ability.get('bkbpierce') if not is_missing(ability.get('bkbpierce')) else '<missing>'}")
        print(f"  dispellable : {ability.get('dispellable') if not is_missing(ability.get('dispellable')) else '<missing>'}")
        print(f"  cooldown    : {'/'.join(levels(ability.get('cd'))) or '<missing>'}")
        print(f"  mana        : {'/'.join(levels(ability.get('mc'))) or '<missing>'}")


if __name__ == "__main__":
    _report()
