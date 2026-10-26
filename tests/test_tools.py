"""Unit tests for the lookup tools.

These encode the Step 2 audit findings as assertions, so a future data
refresh that breaks an assumption fails loudly instead of silently.
"""

import json
from pathlib import Path

import pytest

from src.load_data import is_missing, load_all, real_ability_names
from src.tools import (
    applies_dispel,
    compare_abilities,
    get_ability,
    get_hero,
    is_dispellable,
    pierces_spell_immunity,
)

OVERRIDES = json.loads(
    (Path(__file__).resolve().parent.parent / "src/tools/overrides.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture(scope="module")
def data():
    return load_all()


# --- the headline question -------------------------------------------------


def test_black_hole_pierces_and_comes_from_data():
    r = pierces_spell_immunity("Black Hole")
    assert r["found"]
    (m,) = r["matches"]
    assert m["value"] == "yes"
    assert m["source"] == "dotaconstants"
    assert m["patch_commit"], "every factual answer must name its patch commit"


def test_black_hole_resolves_only_to_enigma():
    """greevil_black_hole and cny2015_black_hole carry different values."""
    keys = [m["key"] for m in get_ability("Black Hole")["matches"]]
    assert keys == ["enigma_black_hole"]


# --- absence must never read as "no" ---------------------------------------


def test_unknown_stays_unknown():
    (m,) = pierces_spell_immunity("Event Horizon")["matches"]
    assert m["value"] == "unknown"
    assert m["value"] != "no"


def test_missing_name_is_not_found():
    r = pierces_spell_immunity("Definitely Not An Ability 123")
    assert r["found"] is False
    assert r["matches"] == []


# --- curated values must be visibly curated --------------------------------


def test_curated_value_is_labelled_and_warns():
    (m,) = pierces_spell_immunity("Bushwhack")["matches"]
    assert m["source"] == "curated"
    assert m["confidence"] in ("high", "medium", "low")
    assert "not from the patch dump" in m["warning"]


def test_empty_list_counts_as_missing_so_override_applies():
    """abaddon_death_coil has bkbpierce == [], not absent. Mist Coil is its
    display name. is_missing() must treat [] as a gap."""
    (m,) = pierces_spell_immunity("Mist Coil")["matches"]
    assert m["source"] == "curated"


def test_real_data_always_wins_over_overrides(data):
    """An override must never shadow a value the dump actually has."""
    shadowed = [
        key
        for key in OVERRIDES["bkbpierce"]
        if not is_missing(data["abilities"][key].get("bkbpierce"))
    ]
    assert shadowed == [], f"overrides shadowing real data: {shadowed}"


def test_every_override_key_is_a_real_hero_ability(data):
    real = set(real_ability_names(data["abilities"], data["hero_abilities"]))
    unknown = [k for k in OVERRIDES["bkbpierce"] if k not in real]
    assert unknown == [], f"override keys not in the real ability set: {unknown}"


def test_override_values_are_from_the_allowed_set():
    allowed = {"yes", "no", "partial", "n/a"}
    bad = {
        k: v["value"]
        for k, v in OVERRIDES["bkbpierce"].items()
        if v["value"] not in allowed
    }
    assert bad == {}


def test_venomous_gale_uses_data_not_curation():
    """Same hero as Snakebite, but this one IS annotated upstream."""
    (m,) = pierces_spell_immunity("Venomous Gale")["matches"]
    assert m["source"] == "dotaconstants"
    assert m["value"] == "no"


# --- aliases ---------------------------------------------------------------


def test_bkb_alias_resolves_to_the_item():
    (m,) = get_ability("BKB")["matches"]
    assert m["key"] == "black_king_bar"
    assert m["kind"] == "item"


def test_pl_alias_resolves_to_the_hero():
    (m,) = get_hero("PL")["matches"]
    assert m["name"] == "Phantom Lancer"


def test_euls_alias_resolves_to_cyclone():
    (m,) = get_ability("Euls")["matches"]
    assert m["key"] == "cyclone"


def test_recipe_items_do_not_shadow_real_items():
    """85 of 501 item keys are recipe_* sharing a display name."""
    keys = [m["key"] for m in get_ability("Lotus Orb")["matches"]]
    assert keys == ["lotus_orb"]


# --- ambiguity is surfaced, never resolved silently ------------------------


def test_shadowraze_returns_all_three():
    r = get_ability("Shadowraze")
    assert r["ambiguous"] is True
    assert len(r["matches"]) == 3
    for m in r["matches"]:
        assert len(m["ambiguous_with"]) == 2


def test_hex_returns_both_heroes():
    r = get_ability("Hex")
    assert r["ambiguous"] is True
    assert {m["hero"] for m in r["matches"]} == {"Lion", "Shadow Shaman"}


# --- dispels ---------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Ice Path", "strong"),
        ("Doom", "none"),
        ("Malefice", "basic"),
        ("Black Hole", "unknown"),
    ],
)
def test_dispellable_mapping(name, expected):
    (m,) = is_dispellable(name)["matches"]
    assert m["removable_by"] == expected


def test_euls_applies_a_basic_dispel_parsed_from_prose():
    (m,) = applies_dispel("Euls")["matches"]
    assert m["applies"] == "basic"
    assert m["parsed_from"] == "free text"


# --- derived interactions: code does the maths, not the LLM ----------------


def test_euls_does_not_dispel_ice_path():
    """basic dispel vs a Strong-Dispels-Only effect, derived arithmetically."""
    c = compare_abilities("Euls", "Ice Path")
    line = next(l for l in c["derived"] if l.startswith("dispel check: Euls"))
    assert ": no --" in line
    assert "weaker" in line


def test_derived_lines_say_which_question_they_answer():
    """Guards against a dispel verdict being read as a reflection answer."""
    c = compare_abilities("Lotus Orb", "Doom")
    assert all(l.startswith("dispel check:") for l in c["derived"])
    assert "reflection" in " ".join(c["not_modelled"]).lower()


def test_compare_refuses_when_nothing_is_derivable():
    c = compare_abilities("Black Hole", "Event Horizon")
    assert c["derived"] == [
        "Not derivable from the available fields. Say so rather than guessing."
    ]


# --- normalisation ---------------------------------------------------------


def test_per_level_values_are_lists_of_strings():
    (m,) = get_ability("Black Hole")["matches"]
    assert m["cooldown"] == ["180", "170", "160"]
    assert m["mana_cost"] == ["300", "400", "500"]


def test_hero_ability_list_excludes_placeholders():
    """generic_hidden has no dname and must not appear."""
    (m,) = get_hero("Enigma")["matches"]
    names = [a["name"] for a in m["abilities"]]
    assert "Black Hole" in names
    assert all(n for n in names)
    assert "generic_hidden" not in [a["key"] for a in m["abilities"]]
