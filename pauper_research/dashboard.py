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

from . import analysis
from .archetypes import UNKNOWN

TEMPLATE = Path(__file__).with_name("dashboard_template.html")
PERIODS = {"30d": 30, "90d": 90, "180d": 180}
TOP_ARCHETYPES = 40      # rows in the archetype table
MATRIX_ARCHETYPES = 25   # max archetypes in the matchup matrix
CARD_ARCHETYPES = 24     # archetypes with a card breakdown
MIN_PLAY_RATE = 0.05     # cards shown in the card view


def _r(x: float, digits: int = 4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), digits)


def _weekly_share(decks: pd.DataFrame, names: list[str], weeks: list[pd.Timestamp]) -> dict[str, list]:
    if decks.empty:
        return {n: [] for n in names}
    week = decks["date"].dt.to_period("W-SUN").dt.start_time
    counts = decks.assign(week=week).groupby(["week", "archetype"]).size().unstack(fill_value=0)
    counts = counts.reindex(weeks, fill_value=0)
    share = counts.div(counts.sum(axis=1).replace(0, math.nan), axis=0)
    return {n: [_r(v, 3) for v in share[n]] if n in share else [None] * len(weeks) for n in names}


def _scope_block(tables: dict[str, pd.DataFrame], colors: dict[str, str], weeks: list[pd.Timestamp]) -> dict:
    decks, matches, events = tables["decks"], tables["matches"], tables["events"]
    summary = analysis.archetype_summary(decks, matches)
    summary = summary[summary["archetype"] != UNKNOWN].head(TOP_ARCHETYPES)
    names = list(summary["archetype"])
    weekly = _weekly_share(decks, names, weeks)

    archetypes = [{
        "name": r.archetype, "color": colors.get(r.archetype, ""), "decks": int(r.decks),
        "share": _r(r.share), "wins": _r(r.wins, 1), "matches": int(r.matches),
        "wr": _r(r.win_rate), "lo": _r(r.ci_low), "hi": _r(r.ci_high), "weekly": weekly[r.archetype],
    } for r in summary.itertuples()]

    matrix_names = names[:MATRIX_ARCHETYPES]
    idx = {n: i for i, n in enumerate(matrix_names)}
    mu = analysis.matchup_table(matches)
    mu = mu[mu["archetype"].isin(idx) & mu["opp_archetype"].isin(idx)]
    matchups = [[idx[r.archetype], idx[r.opp_archetype], _r(r.wins, 1), int(r.matches)] for r in mu.itertuples()]

    by_source = []
    for source, ev in events.groupby("source"):
        by_source.append({
            "source": source, "events": len(ev),
            "decks": int((decks["source"] == source).sum()),
            "matches": int((matches["source"] == source).sum() // 2),
        })
    return {
        "coverage": {"events": len(events), "decks": len(decks), "matches": len(matches) // 2,
                     "by_source": by_source},
        "archetypes": archetypes, "matrix": matrix_names, "matchups": matchups,
    }


def _card_block(tables: dict[str, pd.DataFrame], archetype: str) -> dict:
    decks, deck_cards, matches = tables["decks"], tables["deck_cards"], tables["matches"]
    plays = analysis.card_play_rates(decks, deck_cards, archetype)
    n_decks = int((decks["archetype"] == archetype).sum())
    out = {"decks": n_decks}
    for board in ("main", "side"):
        p = plays[(plays["board"] == board) & (plays["play_rate"] >= MIN_PLAY_RATE)]
        impact = analysis.card_impact(decks, deck_cards, matches, archetype, board)
        imp = impact.set_index("card") if not impact.empty else pd.DataFrame()
        rows = []
        for r in p.itertuples():
            i = imp.loc[r.card] if r.card in imp.index else None
            rows.append([
                r.card, _r(r.play_rate, 3), _r(r.avg_copies, 2),
                None if i is None else int(i.matches_with), None if i is None else _r(i.win_rate_with),
                None if i is None else int(i.matches_without), None if i is None else _r(i.win_rate_without),
                None if i is None else _r(i.delta), None if i is None else _r(i.delta_ci_low),
                None if i is None else _r(i.delta_ci_high),
            ])
        out[board] = rows
    return out


def build_data(all_tables: dict[str, pd.DataFrame]) -> dict:
    decks_all = all_tables["decks"]
    end = decks_all["date"].max().normalize()
    # Most common color per archetype, for the mana pips.
    colors = decks_all.groupby("archetype")["color"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else "")
    colors = colors.to_dict()

    periods = {}
    for key, days in PERIODS.items():
        since = end - timedelta(days=days - 1)
        period_tables = analysis.filter_period(all_tables, since=since.date().isoformat(),
                                               until=end.date().isoformat())
        weeks = list(pd.period_range(since, end, freq="W-SUN").start_time)
        scopes = {s: analysis.filter_period(period_tables, scope=s) for s in analysis.SCOPES}
        blocks = {s: _scope_block(t, colors, weeks) for s, t in scopes.items()}

        card_archs = [a["name"] for a in blocks["combined"]["archetypes"][:CARD_ARCHETYPES]]
        cards = {a: {s: _card_block(t, a) for s, t in scopes.items()} for a in card_archs}
        periods[key] = {
            "since": since.date().isoformat(), "until": end.date().isoformat(),
            "weeks": [w.date().isoformat() for w in weeks],
            "scopes": blocks, "cards": cards,
        }
    return {"generated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"), "periods": periods,
            "default_period": "90d"}


def render(data: dict, standalone: bool = True) -> str:
    """Fill the template. `standalone=False` leaves out the document skeleton
    (doctype, html/head/body), for hosts that add their own."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    if not standalone:
        return page
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + page + '\n</body>\n</html>\n')


def write(all_tables: dict[str, pd.DataFrame], out: Path, standalone: bool = True) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(build_data(all_tables), standalone), encoding="utf-8")
    return out
