"""JSON schemas for the Step 3 functions, plus a name -> callable registry.

Schemas are written out by hand rather than introspected from the functions.
The Ollama Python client can build them from a signature and docstring, but
that makes every docstring edit a silent change to model behaviour. The
description field IS the prompt the model uses to choose a tool, so it is
kept here where that is obvious.
"""

from __future__ import annotations

from ..tools import (
    applies_dispel,
    compare_abilities,
    get_ability,
    get_hero,
    is_dispellable,
    pierces_spell_immunity,
)


def _fn(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "required": required,
                "properties": props,
            },
        },
    }


_ABILITY = {
    "type": "string",
    "description": (
        "Ability, item or hero name as a player would say it. Shorthand like "
        "BKB, Euls, PL or AM is understood."
    ),
}

TOOL_SCHEMAS = [
    _fn(
        "pierces_spell_immunity",
        "Whether an ability or item goes through BKB (spell immunity). Returns "
        "yes, no, partial, n/a or unknown. Use this for any question about BKB, "
        "spell immunity, or whether a spell still works on a BKB'd target.",
        {"ability": _ABILITY},
        ["ability"],
    ),
    _fn(
        "is_dispellable",
        "Whether an effect can be removed by a dispel, and what strength is "
        "needed: basic, strong, none or unknown. Use for questions about "
        "dispelling, removing or cleansing a debuff.",
        {"ability": _ABILITY},
        ["ability"],
    ),
    _fn(
        "applies_dispel",
        "What strength of dispel an item or ability APPLIES when used: basic, "
        "strong or unknown. This is the opposite of is_dispellable. Use it for "
        "the dispelling side of a question, e.g. what Euls or Lotus Orb applies.",
        {"name": _ABILITY},
        ["name"],
    ),
    _fn(
        "get_ability",
        "Full data for an ability or item: description, damage type, cooldown, "
        "mana cost, behaviour and targeting. Use for general questions about "
        "what something does or costs.",
        {"name": _ABILITY},
        ["name"],
    ),
    _fn(
        "get_hero",
        "Base stats and the full ability list for a hero.",
        {"name": {"type": "string", "description": "Hero name or shorthand."}},
        ["name"],
    ),
    _fn(
        "compare_abilities",
        "Side-by-side data for two abilities or items, plus any dispel-strength "
        "verdict that follows arithmetically. Use for interaction questions "
        "involving two things, e.g. does X dispel Y.",
        {"a": _ABILITY, "b": _ABILITY},
        ["a", "b"],
    ),
]

REGISTRY = {
    "pierces_spell_immunity": pierces_spell_immunity,
    "is_dispellable": is_dispellable,
    "applies_dispel": applies_dispel,
    "get_ability": get_ability,
    "get_hero": get_hero,
    "compare_abilities": compare_abilities,
}


def execute(name: str, arguments: dict) -> dict:
    """Run a registered tool. Unknown names and bad arguments become data the
    model has to report, never an exception that kills the CLI."""
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"No such tool: {name}", "available": sorted(REGISTRY)}
    try:
        return fn(**arguments)
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}", "given": arguments}
