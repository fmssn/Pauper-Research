"""Build the interactive dashboard: one self-contained HTML file.

All statistics are precomputed here for a few periods and every scope, and
embedded as JSON. The page itself (dashboard_template.html) only switches
between them and draws.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path

import pandas as pd

from . import analysis, ratings, sources
from .archetypes import UNKNOWN

TEMPLATE = Path(__file__).with_name("dashboard_template.html")
PERIODS = {"30d": 30, "90d": 90, "180d": 180}
TOP_ARCHETYPES = 40      # archetypes listed and used as matchup opponents
CARD_ARCHETYPES = 30     # archetypes with card breakdowns
MIN_PLAY_RATE = 0.05     # cards listed for an archetype

# Card comparisons are only shown when both sides (with / without the card) have
# at least this many decks and matches. Per-matchup comparisons get stricter
# match thresholds relative to their size, but can't ask for as many decks.
OVERALL_MIN = {"min_decks": 5, "min_matches": 15}
MATCHUP_MIN = {"min_decks": 3, "min_matches": 10}
MATCHUP_MIN_TOTAL = 25   # matches needed in a matchup before looking at cards in it


def _r(x: float, digits: int = 4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), digits)


def _w(x: float):
    """Wins can be half (draws); keep them short."""
    x = float(x)
    return int(x) if x.is_integer() else round(x, 1)


def _scope_block(tables: dict[str, pd.DataFrame], colors: dict[str, str], pilot: ratings.PilotFit) -> dict:
    """Every row carries the pilot lift (average, per match) and its bootstrap SD after the raw
    counts, so the page can show raw or pilot-adjusted numbers. Card rows carry the lift with
    and without the card and the SD of their difference."""
    decks, matches, events = tables["decks"], tables["matches"], tables["events"]
    summary = analysis.archetype_summary(decks, matches, pilot)
    summary = summary[summary["archetype"] != UNKNOWN].head(TOP_ARCHETYPES)
    names = list(summary["archetype"])
    idx = {n: i for i, n in enumerate(names)}

    archetypes = [[r.archetype, colors.get(r.archetype, ""), int(r.decks), _r(r.share),
                   _w(0 if pd.isna(r.wins) else r.wins), int(r.matches), _r(r.pilot_lift) or 0, _r(r.lift_sd) or 0]
                  for r in summary.itertuples()]

    mu: dict[int, list] = {}
    table = analysis.matchup_table(matches, pilot=pilot)
    table = table[table["archetype"].isin(idx) & table["opp_archetype"].isin(idx)]
    for r in table.itertuples():
        mu.setdefault(idx[r.archetype], []).append([idx[r.opp_archetype], _w(r.wins), int(r.matches),
                                                    _r(r.pilot_lift), _r(r.lift_sd)])

    cards: dict[int, dict] = {}
    card_mu: dict[int, dict] = {}
    for name in names[:CARD_ARCHETYPES]:
        i = idx[name]
        plays = analysis.card_play_rates(decks, tables["deck_cards"], name)
        block = {}
        for b, board in enumerate(("main", "side")):
            eff = analysis.card_effects(decks, tables["deck_cards"], matches, name, board, pilot=pilot, **OVERALL_MIN)
            eff = eff.set_index("card") if not eff.empty else pd.DataFrame()
            rows = []
            for p in plays[(plays["board"] == board) & (plays["play_rate"] >= MIN_PLAY_RATE)].itertuples():
                row = [p.card, _r(p.play_rate, 3), _r(p.avg_copies, 2)]
                if p.card in eff.index:
                    e = eff.loc[p.card]
                    row += [int(e.decks_with), _w(e.wins_with), int(e.matches_with),
                            int(e.decks_without), _w(e.wins_without), int(e.matches_without),
                            _r(e.lift_with), _r(e.lift_without), _r(e.lift_sd)]
                rows.append(row)
            block[board] = rows

            per_opp = analysis.card_effects(decks, tables["deck_cards"], matches, name, board,
                                            by_opponent=True, pilot=pilot, **MATCHUP_MIN)
            if per_opp.empty:
                continue
            per_opp = per_opp[per_opp["opponent"].isin(idx)]
            sizes = per_opp["matches_with"] + per_opp["matches_without"]
            per_opp = per_opp[sizes >= MATCHUP_MIN_TOTAL]
            for e in per_opp.itertuples():
                card_mu.setdefault(i, {}).setdefault(idx[e.opponent], []).append([
                    e.card, b, int(e.decks_with), _w(e.wins_with), int(e.matches_with),
                    int(e.decks_without), _w(e.wins_without), int(e.matches_without),
                    _r(e.lift_with), _r(e.lift_without), _r(e.lift_sd)])
        block["decks"] = int((decks["archetype"] == name).sum())
        cards[i] = block

    # Skill sensitivity per listed deck (from the 12-month fit, so the same in every period).
    skill = {}
    sk = pilot.skill
    if not sk.empty:
        for name, i in idx.items():
            if name in sk.index and sk.at[name, "matches"] >= ratings.SKILL_MIN_MATCHES \
                    and not pd.isna(sk.at[name, "sensitivity"]):
                r = sk.loc[name]
                skill[i] = [_r(r.sensitivity, 3), _r(r.ci_low, 3), _r(r.ci_high, 3), int(r.matches)]

    # What each source adds to every statistic: decklists drive meta share, non-mirror match
    # rows the win rates, rows with a known opponent the matchups, recency weight the pilot model.
    nm = analysis.non_mirror(matches)
    known = nm[nm["opp_archetype"] != UNKNOWN]
    srcs = sorted(set(events["source"]) | set(decks["source"]) | set(matches["source"]) | set(pilot.weight_by_source))
    by_source = [{"source": src, "events": int((events["source"] == src).sum()),
                  "decks": int((decks["source"] == src).sum()),
                  "matches": int((matches["source"] == src).sum() // 2),
                  "winrate": int((nm["source"] == src).sum()), "matchup": int((known["source"] == src).sum()),
                  "weight": _r(pilot.weight_by_source.get(src, 0.0), 1)}
                 for src in srcs]
    return {
        "coverage": {"events": len(events), "decks": len(decks), "matches": len(matches) // 2,
                     "by_source": by_source},
        "archetypes": archetypes, "mu": mu, "cards": cards, "cardMu": card_mu, "skill": skill,
        "pilot": {"players": pilot.players, "rated": pilot.rated, "lam": _r(pilot.lam)},
    }


def build_data(all_tables: dict[str, pd.DataFrame], bootstrap: int = ratings.BOOTSTRAP) -> dict:
    decks_all = all_tables["decks"]
    end = decks_all["date"].max().normalize()
    # Most common color per archetype, for the mana symbols.
    colors = decks_all.groupby("archetype")["color"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else "")
    colors = colors.to_dict()

    # All periods end on the same day, so one rating fit per scope serves all of them.
    longest = end - timedelta(days=max(PERIODS.values()) - 1)
    pilots = {s: ratings.fit_scope(all_tables, src, end, keep_since=longest, bootstrap=bootstrap)
              for s, src in analysis.SCOPES.items()}

    periods = {}
    for key, days in PERIODS.items():
        since = end - timedelta(days=days - 1)
        period_tables = analysis.filter_period(all_tables, since=since.date().isoformat(),
                                               until=end.date().isoformat())
        periods[key] = {
            "since": since.date().isoformat(), "until": end.date().isoformat(),
            "scopes": {s: _scope_block(analysis.filter_period(period_tables, scope=s), colors, pilots[s])
                       for s in analysis.SCOPES},
        }
    return {"generated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"), "periods": periods,
            "default_period": "90d",
            "thresholds": {"overall": OVERALL_MIN, "matchup": MATCHUP_MIN, "matchupTotal": MATCHUP_MIN_TOTAL,
                           "topArchetypes": TOP_ARCHETYPES, "cardArchetypes": CARD_ARCHETYPES,
                           "minPlayRate": MIN_PLAY_RATE},
            # Settings shown on the methods page.
            "methods": {"lookback_days": ratings.LOOKBACK_DAYS, "half_life_days": ratings.HALF_LIFE_DAYS,
                        "deck_lambda": ratings.DECK_LAMBDA, "lambda_grid": list(ratings.LAMBDA_GRID),
                        "cv_folds": ratings.CV_FOLDS, "bootstrap": bootstrap,
                        "slope_lambda": ratings.SLOPE_LAMBDA, "skill_min_matches": ratings.SKILL_MIN_MATCHES},
            "sources": {"sites": sources.SITES, "repo": sources.DECKLIST_REPO.removesuffix(".git"),
                        "formats": sources.FORMAT_REPO.removesuffix(".git"),
                        "scopes": {s: sorted(v) if v else None for s, v in analysis.SCOPES.items()}}}


def card_names(data: dict) -> list[str]:
    """Every card shown on the page, grouped by deck in popularity order."""
    names: dict[str, None] = {}
    for period in data["periods"].values():
        for block in period["scopes"].values():
            for i in sorted(block["cards"], key=int):
                for board in ("main", "side"):
                    names.update((r[0], None) for r in block["cards"][i][board])
    return list(names)


def render(data: dict, standalone: bool = True) -> str:
    """Fill the template. `standalone=False` leaves out the document skeleton
    (doctype, html/head/body), for hosts that add their own."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    if not standalone:
        return page
    # The template's title, fonts and styles (everything before the marker) go in <head>.
    head, _, body = page.partition("<!--/head-->")
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            + head.strip() + '\n</head>\n<body>\n' + body.strip() + '\n</body>\n</html>\n')


def write(all_tables: dict[str, pd.DataFrame], out: Path, standalone: bool = True,
          images: str | None = "url", bootstrap: int = ratings.BOOTSTRAP) -> Path:
    """Write the page. `images`: "url" links to Scryfall, "sheets" writes image
    sheets to <out dir>/cards/ (for hosts that block other sites), None: no images."""
    from . import scryfall

    data = build_data(all_tables, bootstrap)
    if images == "url":
        data["images"] = scryfall.url_index(card_names(data))
    elif images == "sheets":
        index = scryfall.build_sheets(card_names(data), out.parent / "cards")
        index["base"] = "cards/"
        data["images"] = index
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(data, standalone), encoding="utf-8")
    return out
