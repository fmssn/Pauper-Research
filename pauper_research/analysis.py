"""Metagame, matchup and card-level statistics.

All win rates are *match* win rates, with draws counted as half a win, and
exclude mirror matches. Intervals are 95% Wilson score intervals, which behave
sensibly at the small sample sizes typical of Pauper matchups.

Every table can also be adjusted for pilot skill: pass a `ratings.PilotFit`
as `pilot` and the tables gain the average pilot lift and a pilot-adjusted
win rate (raw minus lift) with its interval. See `ratings`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy import sparse

from .archetypes import UNKNOWN

if TYPE_CHECKING:
    from .ratings import PilotFit

Z = 1.959964  # 95%

# Online and paper events differ a lot: MTGO publishes only top-8 brackets and
# winning lists, while paper sites publish every round. Every statistic can be
# computed for one scope or both combined, so the skew can be compared.
SCOPES: dict[str, set[str] | None] = {
    "online": {"MTGO", "Manatrader"},
    "paper": {"MTGmelee", "CardsRealm", "Topdeck"},
    "combined": None,
}


def wilson(wins: float, n: float, z: float = Z) -> tuple[float, float]:
    if n <= 0:
        return (math.nan, math.nan)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _with_ci(df: pd.DataFrame, wins: str = "wins", n: str = "matches") -> pd.DataFrame:
    df = df.copy()
    df["win_rate"] = df[wins] / df[n]
    bounds = [wilson(w, k) for w, k in zip(df[wins], df[n])]
    df["ci_low"] = [b[0] for b in bounds]
    df["ci_high"] = [b[1] for b in bounds]
    return df


def _widen(centre, lo, hi, new_centre, sd, z: float = Z, clip: bool = True):
    """Move an interval to `new_centre` and add the lift's uncertainty to each side, in quadrature."""
    lo_new = new_centre - np.sqrt((centre - lo) ** 2 + (z * sd) ** 2)
    hi_new = new_centre + np.sqrt((hi - centre) ** 2 + (z * sd) ** 2)
    if clip:
        lo_new, hi_new = np.clip(lo_new, 0.0, 1.0), np.clip(hi_new, 0.0, 1.0)
    return lo_new, hi_new


def _lift_sd(boot: np.ndarray | None, n) -> np.ndarray:
    if boot is None or boot.shape[1] < 2:
        return np.zeros(len(n))
    return boot.std(axis=1, ddof=1) / np.asarray(n, dtype=float)


def _with_pilot(df: pd.DataFrame, nm: pd.DataFrame, keys: list[str], pilot: "PilotFit") -> pd.DataFrame:
    """Add pilot lift and pilot-adjusted win rate to `df`, the `nm.groupby(keys)` table in group order."""
    df = df.copy()
    groups = nm.groupby(keys, sort=True).ngroup().to_numpy()
    point, boot = pilot.sums(nm.index, groups, len(df))
    n = df["matches"].to_numpy(dtype=float)
    df["pilot_lift"] = point / n
    df["lift_sd"] = _lift_sd(boot, n)
    df["adj_win_rate"] = df["win_rate"] - df["pilot_lift"]
    df["adj_ci_low"], df["adj_ci_high"] = _widen(df["win_rate"], df["ci_low"], df["ci_high"],
                                                 df["adj_win_rate"], df["lift_sd"])
    return df


def filter_period(tables: dict[str, pd.DataFrame], since: str | None = None, until: str | None = None,
                  sources: list[str] | None = None, scope: str = "combined") -> dict[str, pd.DataFrame]:
    """Restrict all tables to a date range, a scope (online/paper/combined) and/or a set of sources."""
    if scope not in SCOPES:
        raise ValueError(f"Unknown scope {scope!r}, expected one of {', '.join(SCOPES)}")
    scope_sources = SCOPES[scope]

    def keep(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        mask = pd.Series(True, index=df.index)
        if since:
            mask &= df["date"] >= pd.Timestamp(since)
        if until:
            mask &= df["date"] <= pd.Timestamp(until)
        if sources:
            mask &= df["source"].isin(sources)
        if scope_sources is not None:
            mask &= df["source"].isin(scope_sources)
        return df[mask]

    out = {name: keep(tables[name]) for name in ("events", "decks", "matches")}
    out["deck_cards"] = tables["deck_cards"][tables["deck_cards"]["deck_id"].isin(set(out["decks"]["deck_id"]))]
    return out


def non_mirror(matches: pd.DataFrame) -> pd.DataFrame:
    """Matches where we know our deck and the opponent isn't playing the same archetype.

    Opponents with no published list ("Unknown") are kept: they are almost
    always a different deck, and dropping them would throw away lots of data.
    """
    known = matches[matches["archetype"] != UNKNOWN]
    return known[known["archetype"] != known["opp_archetype"]]


def meta_share(decks: pd.DataFrame) -> pd.DataFrame:
    counts = decks.groupby("archetype").size().rename("decks").reset_index()
    counts["share"] = counts["decks"] / counts["decks"].sum()
    return counts.sort_values("decks", ascending=False, ignore_index=True)


def archetype_summary(decks: pd.DataFrame, matches: pd.DataFrame, pilot: "PilotFit | None" = None) -> pd.DataFrame:
    """Meta share plus non-mirror match win rate for every archetype."""
    share = meta_share(decks)
    nm = non_mirror(matches)
    perf = nm.groupby("archetype").agg(wins=("score", "sum"), matches=("score", "size")).reset_index()
    perf = _with_ci(perf)
    if pilot is not None:
        perf = _with_pilot(perf, nm, ["archetype"], pilot)
    out = share.merge(perf, on="archetype", how="left")
    out["matches"] = out["matches"].fillna(0).astype(int)
    return out


def scope_comparison(tables: dict[str, pd.DataFrame], archetypes: list[str] | None = None) -> pd.DataFrame:
    """Meta share and win rate of each archetype, online vs paper vs combined.

    `tables` should already be filtered by date but not by scope. The `skew`
    column flags archetypes whose online and paper win-rate intervals don't
    overlap, i.e. where the two scenes clearly disagree.
    """
    parts = []
    for scope in SCOPES:
        t = filter_period(tables, scope=scope)
        s = archetype_summary(t["decks"], t["matches"])
        s = s[["archetype", "decks", "share", "matches", "win_rate", "ci_low", "ci_high"]].set_index("archetype")
        parts.append(s.add_prefix(f"{scope}_"))
    out = pd.concat(parts, axis=1)
    if archetypes is not None:
        out = out.reindex(archetypes)
    no_overlap = (out["online_ci_low"] > out["paper_ci_high"]) | (out["paper_ci_low"] > out["online_ci_high"])
    out["skew"] = no_overlap.fillna(False)
    for col in out.columns:
        if col.endswith(("_decks", "_matches")):
            out[col] = out[col].fillna(0).astype(int)
    return out.reset_index(names="archetype")


def matchup_table(matches: pd.DataFrame, min_matches: int = 1, pilot: "PilotFit | None" = None) -> pd.DataFrame:
    """Long-form matchup table: one row per (archetype, opponent archetype)."""
    nm = non_mirror(matches)
    nm = nm[nm["opp_archetype"] != UNKNOWN]
    grouped = _with_ci(nm.groupby(["archetype", "opp_archetype"]).agg(
        wins=("score", "sum"), matches=("score", "size")).reset_index())
    if pilot is not None:
        grouped = _with_pilot(grouped, nm, ["archetype", "opp_archetype"], pilot)
    grouped = grouped[grouped["matches"] >= min_matches]
    return grouped.sort_values(["archetype", "matches"], ascending=[True, False], ignore_index=True)


def matchup_matrix(matchups: pd.DataFrame, archetypes: list[str], value: str = "win_rate") -> pd.DataFrame:
    sub = matchups[matchups["archetype"].isin(archetypes) & matchups["opp_archetype"].isin(archetypes)]
    matrix = sub.pivot(index="archetype", columns="opp_archetype", values=value)
    return matrix.reindex(index=archetypes, columns=archetypes)


def deck_records(matches: pd.DataFrame) -> pd.DataFrame:
    """Non-mirror match record per deck, for card-level analysis."""
    nm = non_mirror(matches).dropna(subset=["deck_id"])
    return nm.groupby("deck_id").agg(wins=("score", "sum"), matches=("score", "size")).reset_index()


def newcombe(w1: float, n1: float, w2: float, n2: float, z: float = Z) -> tuple[float, float]:
    """95% interval for the difference of two proportions (Newcombe's hybrid score method).

    Built from the two Wilson intervals, so it stays sensible at the small,
    lopsided sample sizes typical of card comparisons.
    """
    if n1 <= 0 or n2 <= 0:
        return (math.nan, math.nan)
    p1, p2 = w1 / n1, w2 / n2
    l1, u1 = wilson(w1, n1, z)
    l2, u2 = wilson(w2, n2, z)
    d = p1 - p2
    return (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def card_effects(decks: pd.DataFrame, deck_cards: pd.DataFrame, matches: pd.DataFrame, archetype: str,
                 board: str = "main", by_opponent: bool = False, min_decks: int = 5,
                 min_matches: int = 1, pilot: "PilotFit | None" = None) -> pd.DataFrame:
    """Within one archetype, compare decks that play a card against decks that don't.

    For every card played by some, but not all, decks of the archetype, report
    the non-mirror match win rate with and without it, the difference, and a
    95% interval for the difference. With `by_opponent=True` the comparison is
    done separately for each opposing archetype (column `opponent`).

    A card is kept only when both sides have at least `min_decks` decks and
    `min_matches` matches. Differences are confounded by who plays the card,
    when, and in which events; treat them as leads, not causal effects. With
    `pilot`, the table also has the average pilot lift on each side and the
    difference after removing it (`delta_adj`), which takes pilot skill out of
    that list of confounders.
    """
    arch_ids = set(decks.loc[decks["archetype"] == archetype, "deck_id"])
    nm = non_mirror(matches).dropna(subset=["deck_id"])
    nm = nm[nm["deck_id"].isin(arch_ids)]
    if nm.empty:
        return pd.DataFrame()
    keys = ["opp_archetype", "deck_id"] if by_opponent else ["deck_id"]
    if by_opponent:
        nm = nm[nm["opp_archetype"] != UNKNOWN]
    records = nm.groupby(keys).agg(wins=("score", "sum"), matches=("score", "size")).reset_index()
    records["rec"] = np.arange(len(records))
    group = ["opp_archetype"] if by_opponent else []

    rec_lift, rec_boot = (None, None)
    if pilot is not None:
        rec_lift, rec_boot = pilot.sums(nm.index, nm.groupby(keys, sort=True).ngroup().to_numpy(), len(records))
        records["lift"] = rec_lift

    agg = {"w_tot": ("wins", "sum"), "n_tot": ("matches", "sum"), "d_tot": ("deck_id", "nunique")}
    if pilot is not None:
        agg["l_tot"] = ("lift", "sum")
    if group:
        totals = records.groupby(group).agg(**agg).reset_index()
        totals["tot"] = np.arange(len(totals))
        tot_of_rec = records[group].merge(totals[group + ["tot"]], on=group, how="left")["tot"].to_numpy()
    else:
        totals = pd.DataFrame({k: [records[col].agg(fn)] for k, (col, fn) in agg.items()})
        totals["tot"] = 0
        tot_of_rec = np.zeros(len(records), dtype=int)

    present = deck_cards[(deck_cards["board"] == board) & deck_cards["deck_id"].isin(set(records["deck_id"]))]
    joined = records.merge(present[["deck_id", "card", "count"]], on="deck_id")
    in_agg = {"w_in": ("wins", "sum"), "n_in": ("matches", "sum"), "d_in": ("deck_id", "nunique"),
              "avg_copies": ("count", "mean")}
    if pilot is not None:
        in_agg["l_in"] = ("lift", "sum")
    with_card = joined.groupby(group + ["card"]).agg(**in_agg).reset_index()
    with_card["pos"] = np.arange(len(with_card))
    out = with_card.merge(totals, on=group) if group else with_card.assign(**totals.iloc[0].to_dict())
    out["w_out"] = out["w_tot"] - out["w_in"]
    out["n_out"] = out["n_tot"] - out["n_in"]
    out["d_out"] = out["d_tot"] - out["d_in"]
    out = out[(out["d_in"] >= min_decks) & (out["d_out"] >= min_decks)
              & (out["n_in"] >= min_matches) & (out["n_out"] >= min_matches)]
    if out.empty:
        return pd.DataFrame()

    out = out.assign(
        play_rate=out["d_in"] / out["d_tot"],
        win_rate_with=out["w_in"] / out["n_in"], win_rate_without=out["w_out"] / out["n_out"],
    )
    out["delta"] = out["win_rate_with"] - out["win_rate_without"]
    bounds = [newcombe(a, b, c, d) for a, b, c, d in zip(out["w_in"], out["n_in"], out["w_out"], out["n_out"])]
    out["delta_ci_low"] = [b[0] for b in bounds]
    out["delta_ci_high"] = [b[1] for b in bounds]

    adj_cols = []
    if pilot is not None:
        out["lift_with"] = out["l_in"] / out["n_in"]
        out["lift_without"] = (out["l_tot"] - out["l_in"]) / out["n_out"]
        diff = out["lift_with"] - out["lift_without"]
        sd = np.zeros(len(out))
        if rec_boot is not None and rec_boot.shape[1] >= 2:
            # Bootstrap sums of lift with the card and in total, per (opponent,) card row.
            card_of_row = joined.groupby(group + ["card"], sort=True).ngroup().to_numpy()
            ind = sparse.csr_matrix((np.ones(len(joined)), (card_of_row, joined["rec"].to_numpy())),
                                    shape=(len(with_card), len(records)))
            b_in = np.asarray(ind @ rec_boot)[out["pos"].to_numpy()]
            tot_ind = sparse.csr_matrix((np.ones(len(records)), (tot_of_rec, np.arange(len(records)))),
                                        shape=(len(totals), len(records)))
            b_tot = np.asarray(tot_ind @ rec_boot)[out["tot"].to_numpy(dtype=int)]
            n_in, n_out = out["n_in"].to_numpy(float)[:, None], out["n_out"].to_numpy(float)[:, None]
            sd = (b_in / n_in - (b_tot - b_in) / n_out).std(axis=1, ddof=1)
        out["lift_sd"] = sd
        out["delta_adj"] = out["delta"] - diff
        out["delta_adj_ci_low"], out["delta_adj_ci_high"] = _widen(
            out["delta"], out["delta_ci_low"], out["delta_ci_high"], out["delta_adj"], sd, clip=False)
        adj_cols = ["lift_with", "lift_without", "lift_sd", "delta_adj", "delta_adj_ci_low", "delta_adj_ci_high"]

    out = out.rename(columns={"opp_archetype": "opponent", "d_in": "decks_with", "d_out": "decks_without",
                              "n_in": "matches_with", "n_out": "matches_without",
                              "w_in": "wins_with", "w_out": "wins_without"})
    cols = (["opponent"] if by_opponent else []) + [
        "card", "decks_with", "decks_without", "play_rate", "avg_copies", "wins_with", "matches_with",
        "wins_without", "matches_without", "win_rate_with", "win_rate_without", "delta",
        "delta_ci_low", "delta_ci_high"] + adj_cols
    out = out[cols]
    for c in ("decks_with", "decks_without", "matches_with", "matches_without"):
        out[c] = out[c].astype(int)
    sort_by = "delta_adj" if pilot is not None else "delta"
    return out.sort_values((["opponent"] if by_opponent else []) + [sort_by],
                           ascending=([True] if by_opponent else []) + [False], ignore_index=True)


def card_impact(decks: pd.DataFrame, deck_cards: pd.DataFrame, matches: pd.DataFrame, archetype: str,
                board: str = "main", min_decks: int = 5, pilot: "PilotFit | None" = None) -> pd.DataFrame:
    """Card comparison across all of an archetype's matches. See `card_effects`."""
    return card_effects(decks, deck_cards, matches, archetype, board, by_opponent=False, min_decks=min_decks,
                        pilot=pilot)


def card_play_rates(decks: pd.DataFrame, deck_cards: pd.DataFrame, archetype: str) -> pd.DataFrame:
    """How often each card shows up in an archetype, and with how many copies."""
    ids = decks.loc[decks["archetype"] == archetype, "deck_id"]
    n = len(ids)
    sub = deck_cards[deck_cards["deck_id"].isin(set(ids))]
    out = sub.groupby(["board", "card"]).agg(decks=("deck_id", "nunique"), avg_copies=("count", "mean")).reset_index()
    out["play_rate"] = out["decks"] / max(n, 1)
    return out.sort_values(["board", "play_rate"], ascending=[True, False], ignore_index=True)

