"""Rules-based archetype detection.

A Python port of Badaro's MTGOArchetypeParser
(https://github.com/Badaro/MTGOArchetypeParser), reading the community-maintained
definitions from MTGOFormatData/Formats/Pauper. Keeping the upstream rules means
our archetype names line up with other tools that use the same definitions.

Behaviour that differs from upstream: when several archetypes match we always
pick the one with the fewest conditions (upstream's "PreferSimpler" mode)
instead of returning "Conflict(...)", but we keep the full list of matches so
conflicts can be audited.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

COLOR_NAMES = {
    "W": "Mono White", "U": "Mono Blue", "B": "Mono Black", "R": "Mono Red", "G": "Mono Green",
    "WU": "Azorius", "WB": "Orzhov", "WR": "Boros", "WG": "Selesnya", "UB": "Dimir",
    "UR": "Izzet", "UG": "Simic", "BR": "Rakdos", "BG": "Golgari", "RG": "Gruul",
    "WUB": "Esper", "WUR": "Jeskai", "WUG": "Bant", "WBR": "Mardu", "WBG": "Abzan",
    "WRG": "Naya", "UBR": "Grixis", "UBG": "Sultai", "URG": "Temur", "BRG": "Jund",
    "WUBR": "WUBR", "WBRG": "WBRG", "WUBG": "WUBG", "WURG": "WURG", "UBRG": "UBRG",
    "WUBRG": "5c", "C": "Colorless",
}

UNKNOWN = "Unknown"


@dataclass
class Condition:
    type: str
    cards: list[str]

    def test(self, main: dict[str, int], side: dict[str, int]) -> bool:
        cards = self.cards
        first = cards[0]
        t = self.type
        if t == "InMainboard":
            return first in main
        if t == "InSideboard":
            return first in side
        if t == "InMainOrSideboard":
            return first in main or first in side
        if t == "OneOrMoreInMainboard":
            return any(c in main for c in cards)
        if t == "OneOrMoreInSideboard":
            return any(c in side for c in cards)
        if t == "OneOrMoreInMainOrSideboard":
            return any(c in main or c in side for c in cards)
        # "TwoOrMore" counts distinct listed cards present, not copies.
        if t == "TwoOrMoreInMainboard":
            return sum(c in main for c in cards) >= 2
        if t == "TwoOrMoreInSideboard":
            return sum(c in side for c in cards) >= 2
        if t == "TwoOrMoreInMainOrSideboard":
            return sum(c in main for c in cards) + sum(c in side for c in cards) >= 2
        if t == "DoesNotContain":
            return first not in main and first not in side
        if t == "DoesNotContainMainboard":
            return first not in main
        if t == "DoesNotContainSideboard":
            return first not in side
        raise ValueError(f"Unknown condition type: {t}")


@dataclass
class Archetype:
    name: str
    include_color: bool
    conditions: list[Condition] = field(default_factory=list)
    variants: list["Archetype"] = field(default_factory=list)
    common_cards: list[str] = field(default_factory=list)  # fallbacks only

    def matches(self, main: dict[str, int], side: dict[str, int]) -> bool:
        return all(c.test(main, side) for c in self.conditions)

    def display_name(self, color: str) -> str:
        name = self.name.replace("Generic", "")
        if self.include_color:
            name = f"{COLOR_NAMES[color]} {name}"
        # Split PascalCase names like "MonoBlueTerror", as upstream does.
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
        return re.sub(r"\s+", " ", name).strip()


@dataclass
class Detection:
    archetype: str
    color: str
    candidates: list[str]  # every specific archetype that matched (len > 1 => conflict)
    is_fallback: bool


def _parse_archetype(data: dict) -> Archetype:
    return Archetype(
        name=data["Name"],
        include_color=bool(data.get("IncludeColorInName")),
        # Upstream skips conditions with an empty card list.
        conditions=[Condition(c["Type"], c["Cards"]) for c in data.get("Conditions") or [] if c.get("Cards")],
        variants=[_parse_archetype(v) for v in data.get("Variants") or []],
        common_cards=list(data.get("CommonCards") or []),
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


class Classifier:
    def __init__(self, archetypes: list[Archetype], fallbacks: list[Archetype],
                 land_colors: dict[str, str], card_colors: dict[str, str], min_similarity: float = 0.1):
        self.archetypes = archetypes
        self.fallbacks = fallbacks
        self.land_colors = land_colors
        self.card_colors = card_colors
        self.min_similarity = min_similarity

    @classmethod
    def from_format_data(cls, root: Path, fmt: str = "Pauper") -> "Classifier":
        fmt_dir = root / "Formats" / fmt
        lands: dict[str, str] = {}
        nonlands: dict[str, str] = {}
        for colors_file in (root / "Formats" / "card_colors.json", fmt_dir / "color_overrides.json"):
            if not colors_file.exists():
                continue
            data = _read_json(colors_file)
            for entry in data.get("Lands") or []:
                lands[entry["Name"]] = entry["Color"]
            for entry in data.get("NonLands") or []:
                nonlands[entry["Name"]] = entry["Color"]
        archetypes = [_parse_archetype(_read_json(p)) for p in sorted((fmt_dir / "Archetypes").glob("*.json"))]
        fallbacks = [_parse_archetype(_read_json(p)) for p in sorted((fmt_dir / "Fallbacks").glob("*.json"))]
        return cls(archetypes, fallbacks, lands, nonlands)

    def color(self, main: dict[str, int], side: dict[str, int]) -> str:
        """A deck has a color if it plays both lands and spells of that color."""
        in_lands = dict.fromkeys("WUBRG", 0)
        in_spells = dict.fromkeys("WUBRG", 0)
        for board in (main, side):
            for card, count in board.items():
                for c in self.land_colors.get(card, ""):
                    if c in in_lands:
                        in_lands[c] += count
                for c in self.card_colors.get(card, ""):
                    if c in in_spells:
                        in_spells[c] += count
        color = "".join(c for c in "WUBRG" if in_lands[c] and in_spells[c])
        return color or "C"

    def detect(self, main: dict[str, int], side: dict[str, int]) -> Detection:
        color = self.color(main, side)
        hits: list[tuple[int, str]] = []
        for arch in self.archetypes:
            if not arch.matches(main, side):
                continue
            variants = [v for v in arch.variants if v.matches(main, side)]
            if variants:
                for v in variants:
                    hits.append((len(arch.conditions) + len(v.conditions), v.display_name(color)))
            else:
                hits.append((len(arch.conditions), arch.display_name(color)))

        if hits:
            # Stable sort keeps file order on ties, matching upstream's OrderBy.Take(1).
            hits.sort(key=lambda h: h[0])
            return Detection(hits[0][1], color, [h[1] for h in hits], is_fallback=False)

        fallback = self._best_fallback(main, side)
        if fallback is not None:
            return Detection(fallback.display_name(color), color, [], is_fallback=True)
        return Detection(UNKNOWN, color, [], is_fallback=False)

    def _best_fallback(self, main: dict[str, int], side: dict[str, int]) -> Archetype | None:
        best, best_weight = None, 0
        for fb in self.fallbacks:
            common = set(fb.common_cards)
            weight = sum(n for c, n in main.items() if c in common) + sum(n for c, n in side.items() if c in common)
            # Ties go to the fallback with fewer common cards, as upstream.
            if weight > best_weight or (weight == best_weight and best is not None and weight > 0
                                        and len(fb.common_cards) < len(best.common_cards)):
                best, best_weight = fb, weight
        if best is None:
            return None
        # Upstream divides by the number of distinct card entries, not card count.
        similarity = best_weight / max(1, len(main) + len(side))
        return best if similarity > self.min_similarity else None
