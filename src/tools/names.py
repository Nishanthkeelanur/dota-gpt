"""Name resolution: plain English in, dotaconstants keys out.

This is the foundation of every other tool, and the easiest place to be
subtly wrong. Two traps the audit in Step 2 turned up:

1. abilities.json holds ~3100 entries, but only 789 belong to a playable
   hero. The rest are event reskins (greevil_black_hole, cny2015_black_hole
   -- which carry DIFFERENT values to the real one), talent rows and engine
   stubs. We index only the real 789, so junk is unreachable by construction.
2. 85 of the 501 item keys are recipe_* entries that share a display name
   with the real item. Loose matching lands on the recipe.

Display names are also not unique: 'Shadowraze' maps to three abilities,
'Hex' to both Lion's and Shadow Shaman's. Resolution therefore returns a
LIST of candidates and never silently picks one.
"""

from __future__ import annotations

from ..load_data import load_all, real_ability_names

# Shorthand players actually type. Maps to the canonical display name, which
# the resolver then looks up normally -- so an alias can never point at a key
# that has gone away.
ALIASES: dict[str, str] = {
    # items
    "bkb": "Black King Bar",
    "euls": "Eul's Scepter of Divinity",
    "eul's": "Eul's Scepter of Divinity",
    "lotus": "Lotus Orb",
    "blink dagger": "Blink Dagger",
    "butterfly": "Butterfly",
    "aghs": "Aghanim's Scepter",
    "scepter": "Aghanim's Scepter",
    "shard": "Aghanim's Shard",
    "linkens": "Linken's Sphere",
    "manta": "Manta Style",
    "satanic": "Satanic",
    "mkb": "Monkey King Bar",
    "sny": "Sange and Yasha",
    "vlads": "Vladmir's Offering",
    # heroes
    "pl": "Phantom Lancer",
    "pa": "Phantom Assassin",
    "am": "Anti-Mage",
    "sf": "Shadow Fiend",
    "wk": "Wraith King",
    "qop": "Queen of Pain",
    "cm": "Crystal Maiden",
    "ck": "Chaos Knight",
    "od": "Outworld Devourer",
    "sd": "Shadow Demon",
    "ta": "Templar Assassin",
    "np": "Nature's Prophet",
    "furion": "Nature's Prophet",
    "wr": "Windranger",
    "ns": "Night Stalker",
    "es": "Earthshaker",
    "sk": "Sand King",
    "tb": "Terrorblade",
    "mk": "Monkey King",
    "lc": "Legion Commander",
    "dk": "Dragon Knight",
    "ursa": "Ursa",
    "void": "Faceless Void",
    "necro": "Necrophos",
    "veno": "Venomancer",
    "slark": "Slark",
    "treant": "Treant Protector",
    "wd": "Witch Doctor",
    "sb": "Spirit Breaker",
    "bh": "Bounty Hunter",
    "zeus": "Zeus",
    "magnus": "Magnus",
    "tiny": "Tiny",
    "enigma": "Enigma",
    "doom": "Doom",
    "jakiro": "Jakiro",
}


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("'", "'").split())


class Index:
    """Lazily built lookup tables over the dumps."""

    def __init__(self, data: dict | None = None) -> None:
        self.data = data if data is not None else load_all()
        ab = self.data["abilities"]
        self.real = real_ability_names(ab, self.data["hero_abilities"])

        # ability key -> owning hero display name
        self.owner: dict[str, str] = {}
        hero_key_to_name = {
            h["name"]: h.get("localized_name", h["name"])
            for h in self.data["heroes"].values()
            if "name" in h
        }
        for hero_key, entry in self.data["hero_abilities"].items():
            for a in entry.get("abilities", []):
                self.owner.setdefault(a, hero_key_to_name.get(hero_key, hero_key))

        # display name -> [ability keys]
        self.ability_by_name: dict[str, list[str]] = {}
        for a in self.real:
            dname = ab[a].get("dname")
            if dname:
                self.ability_by_name.setdefault(_norm(dname), []).append(a)

        # display name -> [item keys], real items only
        self.item_by_name: dict[str, list[str]] = {}
        for key, item in self.data["items"].items():
            if key.startswith("recipe_"):
                continue
            dname = item.get("dname")
            if dname:
                self.item_by_name.setdefault(_norm(dname), []).append(key)

        # display name -> hero key
        self.hero_by_name: dict[str, str] = {
            _norm(h["localized_name"]): h["name"]
            for h in self.data["heroes"].values()
            if h.get("localized_name") and h.get("name")
        }

    # --- resolution --------------------------------------------------------

    def resolve(self, query: str) -> list[dict]:
        """All plausible matches for a query, best kind first.

        Returns a list of {"kind", "key", "dname", "hero"} dicts. Empty list
        means no match -- callers must treat that as "unknown", not "no".
        """
        q = _norm(query)
        q = _norm(ALIASES.get(q, q))
        out: list[dict] = []

        for key in self.ability_by_name.get(q, []):
            out.append(
                {
                    "kind": "ability",
                    "key": key,
                    "dname": self.data["abilities"][key].get("dname"),
                    "hero": self.owner.get(key),
                }
            )
        for key in self.item_by_name.get(q, []):
            out.append(
                {
                    "kind": "item",
                    "key": key,
                    "dname": self.data["items"][key].get("dname"),
                    "hero": None,
                }
            )
        if q in self.hero_by_name:
            key = self.hero_by_name[q]
            out.append(
                {
                    "kind": "hero",
                    "key": key,
                    "dname": self.data["heroes"][str(_hero_id(self.data, key))].get(
                        "localized_name"
                    )
                    if _hero_id(self.data, key)
                    else query,
                    "hero": None,
                }
            )

        if out:
            return out
        return self._fuzzy(q)

    def _fuzzy(self, q: str) -> list[dict]:
        """Substring fallback. Deliberately dumb and deliberately last."""
        out = []
        for table, kind in (
            (self.ability_by_name, "ability"),
            (self.item_by_name, "item"),
        ):
            for name, keys in table.items():
                if q and (q in name or name in q):
                    for key in keys:
                        out.append(
                            {
                                "kind": kind,
                                "key": key,
                                "dname": name,
                                "hero": self.owner.get(key),
                                "fuzzy": True,
                            }
                        )
        return out[:10]


def _hero_id(data: dict, hero_key: str) -> str | None:
    for hid, h in data["heroes"].items():
        if h.get("name") == hero_key:
            return hid
    return None


_INDEX: Index | None = None


def index() -> Index:
    """Process-wide index. Built once; the dumps never change at runtime."""
    global _INDEX
    if _INDEX is None:
        _INDEX = Index()
    return _INDEX
