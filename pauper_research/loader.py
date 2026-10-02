"""Turn the decklist cache JSON into flat tables.

Tables produced (all pandas DataFrames):

events      one row per tournament
decks       one row per published decklist, with its archetype
deck_cards  one row per (deck, card, board) - the basis for card-level analysis
matches     one row per match *from each player's side* (so every match appears
            twice, once per player). This makes per-deck and per-archetype win
            rates a simple groupby.

What each source gives us (as of 2026):

* MTGmelee, Topdeck, CardsRealm: every Swiss and playoff round, and decklists
  for most players. This is where most of the matchup data comes from.
* MTGO Challenges: only the top-8 playoff bracket, plus top-32 decklists.
  (Since mid-2024 mtgo.com no longer publishes Swiss pairings.)
* MTGO Leagues: a curated sample of 5-0 lists, no opponents. Useful for meta
  share among winning decks only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .archetypes import UNKNOWN, Classifier

BYE_NAMES = {"-", "", "BYE", "Bye", "bye"}


def _iter_tournament_files(root: Path):
    yield from sorted((root / "Tournaments").rglob("*.json"))


def _source_of(path: Path, root: Path) -> str:
    return path.relative_to(root / "Tournaments").parts[0]


def _event_type(source: str, name: str) -> str:
    lowered = name.lower()
    if source == "MTGO":
        for kind in ("challenge", "league", "qualifier", "showcase", "preliminary"):
            if kind in lowered:
                return kind
        return "other"
    return "paper" if source in {"MTGmelee", "Topdeck", "CardsRealm"} else "other"


def _parse_result(result: str) -> tuple[int, int, int] | None:
    parts = result.split("-")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def load(decklist_root: Path, classifier: Classifier, fmt: str = "Pauper") -> dict[str, pd.DataFrame]:
    events, decks, cards, matches = [], [], [], []
    seen_uris: set[str] = set()

    for path in _iter_tournament_files(decklist_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        tour = data.get("Tournament") or {}
        if (tour.get("Formats") or "").lower() != fmt.lower():
            continue
        uri = tour.get("Uri") or str(path)
        # The cache occasionally stores the same event under two paths.
        if uri in seen_uris:
            continue
        seen_uris.add(uri)

        source = _source_of(path, decklist_root)
        event_id = len(events)
        date = pd.to_datetime(str(tour.get("Date"))[:10], errors="coerce")
        events.append({
            "event_id": event_id, "date": date, "name": tour.get("Name"), "source": source,
            "event_type": _event_type(source, tour.get("Name") or ""), "uri": uri,
            "players": len(data.get("Standings") or data.get("Decks") or []),
        })

        player_deck: dict[str, int] = {}
        for deck in data.get("Decks") or []:
            main = {c["CardName"]: c["Count"] for c in deck.get("Mainboard") or []}
            side = {c["CardName"]: c["Count"] for c in deck.get("Sideboard") or []}
            if not main:
                continue
            detection = classifier.detect(main, side)
            deck_id = len(decks)
            player = deck.get("Player")
            player_deck[player] = deck_id
            decks.append({
                "deck_id": deck_id, "event_id": event_id, "date": date, "source": source,
                "player": player, "result": deck.get("Result"),
                "archetype": detection.archetype, "color": detection.color,
                "is_fallback": detection.is_fallback, "is_conflict": len(detection.candidates) > 1,
                "candidates": "|".join(detection.candidates),
            })
            for board, items in (("main", main), ("side", side)):
                for card, count in items.items():
                    cards.append({"deck_id": deck_id, "card": card, "board": board, "count": count})

        for rnd in data.get("Rounds") or []:
            for m in rnd.get("Matches") or []:
                p1, p2 = m.get("Player1"), m.get("Player2")
                parsed = _parse_result(m.get("Result") or "")
                if parsed is None or p2 in BYE_NAMES or p1 in BYE_NAMES or sum(parsed) == 0:
                    continue
                g1, g2, gd = parsed
                for me, opp, gw, gl in ((p1, p2, g1, g2), (p2, p1, g2, g1)):
                    score = 1.0 if gw > gl else 0.0 if gw < gl else 0.5
                    matches.append({
                        "event_id": event_id, "date": date, "source": source,
                        "round": rnd.get("RoundName"),
                        "player": me, "opponent": opp,
                        "deck_id": player_deck.get(me), "opp_deck_id": player_deck.get(opp),
                        "games_won": gw, "games_lost": gl, "games_drawn": gd, "score": score,
                    })

    events_df = pd.DataFrame(events)
    decks_df = pd.DataFrame(decks)
    cards_df = pd.DataFrame(cards)
    matches_df = pd.DataFrame(matches)

    if not matches_df.empty and not decks_df.empty:
        arch = decks_df.set_index("deck_id")["archetype"]
        matches_df["deck_id"] = matches_df["deck_id"].astype("Int64")
        matches_df["opp_deck_id"] = matches_df["opp_deck_id"].astype("Int64")
        matches_df["archetype"] = matches_df["deck_id"].map(arch).fillna(UNKNOWN)
        matches_df["opp_archetype"] = matches_df["opp_deck_id"].map(arch).fillna(UNKNOWN)

    return {"events": events_df, "decks": decks_df, "deck_cards": cards_df, "matches": matches_df}
