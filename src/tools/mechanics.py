"""The lookup functions the LLM is allowed to call.

Design rules, from the CLAUDE.md design-principles section:

* Every return value carries its own provenance. "source" is "dotaconstants"
  (read from the patch dumps) or "curated" (hand-entered, see overrides.json).
  The agent must repeat that distinction to the user.
* Absence is "unknown", never "no". The Step 2 audit found bkbpierce missing
  on 275 of 789 hero abilities and dispellable on 333 -- inferring "no" from
  a gap would make the tool confidently wrong.
* Ambiguous names return every candidate. "Shadowraze" is three abilities and
  "Hex" belongs to two different heroes; picking one silently is the failure
  mode that matters most.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..load_data import as_list, is_missing, levels, source_commit
from .names import index

OVERRIDES_PATH = Path(__file__).resolve().parent / "overrides.json"

_DISPEL_RE = re.compile(r"Dispel Type:\s*(Basic|Strong)\s*Dispel", re.I)

_DISPELLABLE_MAP = {
    "yes": "basic",
    "no": "none",
    "strong dispels only": "strong",
}


def _overrides() -> dict:
    with OVERRIDES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _provenance(source: str) -> dict:
    p = source_commit()
    return {
        "source": source,
        "patch_commit": p["commit"],
        "patch_commit_date": p["commit_date"],
    }


def _raw(ix, match: dict) -> dict:
    table = ix.data["abilities"] if match["kind"] == "ability" else ix.data["items"]
    return table[match["key"]]


def _item_desc(raw: dict):
    parts = []
    for a in raw.get("abilities") or []:
        title, desc = a.get("title", ""), a.get("description", "")
        joined = f"{title}: {desc}" if title and desc else (title or desc)
        if joined:
            parts.append(joined)
    return "\n".join(parts) or None


def _castables(name: str):
    ix = index()
    return ix, [m for m in ix.resolve(name) if m["kind"] in ("ability", "item")]


def get_hero(name: str) -> dict:
    """Stats plus ability list for a hero."""
    ix = index()
    matches = [m for m in ix.resolve(name) if m["kind"] == "hero"]
    if not matches:
        return {"query": name, "found": False, "matches": []}

    out = []
    for m in matches:
        hero = next(
            (h for h in ix.data["heroes"].values() if h.get("name") == m["key"]), None
        )
        if hero is None:
            continue
        entry = ix.data["hero_abilities"].get(m["key"], {})
        abilities = []
        for a in entry.get("abilities", []):
            ability = ix.data["abilities"].get(a)
            if ability is None or not ability.get("dname"):
                continue
            abilities.append({"key": a, "name": ability["dname"]})
        out.append(
            {
                "name": hero.get("localized_name"),
                "key": m["key"],
                "primary_attr": hero.get("primary_attr"),
                "attack_type": hero.get("attack_type"),
                "roles": hero.get("roles", []),
                "base_health": hero.get("base_health"),
                "base_armor": hero.get("base_armor"),
                "base_mr": hero.get("base_mr"),
                "move_speed": hero.get("move_speed"),
                "abilities": abilities,
            }
        )
    return {
        "query": name,
        "found": True,
        "matches": out,
        **_provenance("dotaconstants"),
    }


def get_ability(name: str) -> dict:
    """Full data for an ability or item, every candidate included."""
    ix, matches = _castables(name)
    if not matches:
        return {"query": name, "found": False, "matches": []}

    out = []
    for m in matches:
        raw = _raw(ix, m)
        out.append(
            {
                "key": m["key"],
                "kind": m["kind"],
                "name": raw.get("dname"),
                "hero": m.get("hero"),
                "description": raw.get("desc") or _item_desc(raw),
                "behavior": as_list(raw.get("behavior")),
                "damage_type": None
                if is_missing(raw.get("dmg_type"))
                else raw["dmg_type"],
                "cooldown": levels(raw.get("cd")),
                "mana_cost": levels(raw.get("mc")),
                "target_team": as_list(raw.get("target_team")),
                "ambiguous_with": [o["key"] for o in matches if o["key"] != m["key"]],
            }
        )
    return {
        "query": name,
        "found": True,
        "ambiguous": len(out) > 1,
        "matches": out,
        **_provenance("dotaconstants"),
    }


def pierces_spell_immunity(ability: str) -> dict:
    """Does it go through BKB? yes / no / partial / n/a / unknown."""
    ix, matches = _castables(ability)
    if not matches:
        return {"query": ability, "found": False, "matches": []}

    overrides = _overrides()["bkbpierce"]
    out = []
    for m in matches:
        raw = _raw(ix, m)
        value = raw.get("bkbpierce")

        if not is_missing(value):
            row = {
                "value": str(value).lower(),
                "confidence": "high",
                "note": None,
                **_provenance("dotaconstants"),
            }
        elif m["key"] in overrides:
            curated = overrides[m["key"]]
            row = {
                "value": curated["value"],
                "confidence": curated["confidence"],
                "note": curated["note"],
                **_provenance("curated"),
                "warning": "Hand-entered value, not from the patch dump. Say so.",
            }
        else:
            row = {
                "value": "unknown",
                "confidence": None,
                "note": (
                    "The patch dump has no spell-immunity value for this and "
                    "it is not curated. Do not guess."
                ),
                **_provenance("dotaconstants"),
            }

        out.append(
            {
                "ability": raw.get("dname") or m["key"],
                "key": m["key"],
                "hero": m.get("hero"),
                **row,
            }
        )

    return {"query": ability, "found": True, "ambiguous": len(out) > 1, "matches": out}


def is_dispellable(ability: str) -> dict:
    """Can the effect be removed? basic / strong / none / unknown."""
    ix, matches = _castables(ability)
    if not matches:
        return {"query": ability, "found": False, "matches": []}

    out = []
    for m in matches:
        raw = _raw(ix, m)
        value = raw.get("dispellable")
        removable = (
            "unknown"
            if is_missing(value)
            else _DISPELLABLE_MAP.get(str(value).strip().lower(), "unknown")
        )
        out.append(
            {
                "ability": raw.get("dname") or m["key"],
                "key": m["key"],
                "hero": m.get("hero"),
                "removable_by": removable,
                "raw_value": None if is_missing(value) else value,
                "note": (
                    "No dispellable value in the patch dump. Do not guess."
                    if removable == "unknown"
                    else None
                ),
                **_provenance("dotaconstants"),
            }
        )
    return {"query": ability, "found": True, "ambiguous": len(out) > 1, "matches": out}


def applies_dispel(name: str) -> dict:
    """What strength of dispel does this APPLY? basic / strong / unknown.

    NOT in the CLAUDE.md spec. Added because it is required to answer the
    build-order example about whether Euls dispels an Ice Path stun: that
    needs the dispel Euls applies (basic) against what Ice Path requires
    (strong). is_dispellable answers the opposite question and cannot
    substitute for it.

    Only items declare this, and only in prose, so this parses free text.
    """
    ix, matches = _castables(name)
    if not matches:
        return {"query": name, "found": False, "matches": []}

    out = []
    for m in matches:
        raw = _raw(ix, m)
        blob = _item_desc(raw) or raw.get("desc") or ""
        hit = _DISPEL_RE.search(blob)
        out.append(
            {
                "name": raw.get("dname") or m["key"],
                "key": m["key"],
                "applies": hit.group(1).lower() if hit else "unknown",
                "parsed_from": "free text" if hit else None,
                "note": (
                    None
                    if hit
                    else "No Dispel Type string found. Only 15 items declare one."
                ),
                **_provenance("dotaconstants"),
            }
        )
    return {"query": name, "found": True, "matches": out}


def compare_abilities(a: str, b: str) -> dict:
    """Side-by-side for interaction questions, plus any derived verdict.

    The derivation is deliberately code, not LLM inference: if one side
    applies a dispel and the other states what strength it requires, the
    answer follows arithmetically.
    """
    rank = {"basic": 1, "strong": 2}

    def side(name: str) -> dict:
        return {
            "ability": get_ability(name),
            "pierces": pierces_spell_immunity(name),
            "dispellable": is_dispellable(name),
            "applies_dispel": applies_dispel(name),
        }

    left, right = side(a), side(b)

    derived = []
    pairs = (
        (left, right, "dispel check: " + a + " used on " + b),
        (right, left, "dispel check: " + b + " used on " + a),
    )
    for first, second, label in pairs:
        applied = next(
            (
                m["applies"]
                for m in first["applies_dispel"].get("matches", [])
                if m["applies"] != "unknown"
            ),
            None,
        )
        required = next(
            (
                m["removable_by"]
                for m in second["dispellable"].get("matches", [])
                if m["removable_by"] != "unknown"
            ),
            None,
        )
        if not (applied and required):
            continue
        if required == "none":
            derived.append(
                label + ": no -- that effect cannot be dispelled at all."
            )
        elif rank.get(applied, 0) >= rank.get(required, 99):
            derived.append(
                label + ": yes -- a " + applied + " dispel meets the "
                + required + " requirement."
            )
        else:
            derived.append(
                label + ": no -- a " + applied + " dispel is weaker than the "
                + required + " requirement."
            )

    return {
        "left": left,
        "right": right,
        "derived": derived
        or ["Not derivable from the available fields. Say so rather than guessing."],
        "not_modelled": [
            "Spell reflection (Lotus Orb, Linkens Sphere): no field or text",
            "in the dumps states which spells are reflectable.",
            "Any interaction not reducible to dispel strength or immunity.",
        ],
        "derived_answers_only": (
            "Every line in derived is a DISPEL-STRENGTH verdict and nothing "
            "else. It does not answer reflection, blocking, or any other "
            "interaction. If the question was about something else, say the "
            "data does not cover it."
        ),
        **_provenance("dotaconstants"),
    }
