"""Lookup tools the LLM may call. See mechanics.py for the design rules."""

from .mechanics import (
    applies_dispel,
    compare_abilities,
    get_ability,
    get_hero,
    is_dispellable,
    pierces_spell_immunity,
)
from .names import ALIASES, index

__all__ = [
    "get_hero",
    "get_ability",
    "pierces_spell_immunity",
    "is_dispellable",
    "applies_dispel",
    "compare_abilities",
    "index",
    "ALIASES",
]
