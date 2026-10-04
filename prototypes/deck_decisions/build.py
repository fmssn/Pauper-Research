"""Prototype: which cards in a deck are fixed, and which are real deckbuilding decisions.

Builds data.js for prototypes/deck_decisions/index.html, per archetype and board:

  A  Decisions       - fixed core, copy-count decisions, slots (cards whose summed copies
                       stay constant) and in/out cards with what they replace.
  C  Shells          - a divisive tree of single-card questions ("4 Ephemerate?") chosen so
                       each answer predicts the rest of the list best; leaves are shells.

Every split / side gets a pilot-adjusted win rate (raw minus average pilot lift, no bootstrap).

Run:  .venv/Scripts/python prototypes/deck_decisions/build.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pauper_research import analysis, ratings  # noqa: E402
from pauper_research.archetypes import UNKNOWN  # noqa: E402

OUT = Path(__file__).with_name("data.js")
DAYS = 90
N_ARCHETYPES = 16
MIN_LISTS = 80
CORE_PLAY = 0.85        # same as the dashboard
FLEX_MIN_PLAY = 0.08    # below: "spice"
MIN_CARD_LISTS = 5
SWAP_PHI = -0.15        # pairs at least this exclusive are "swaps"
SWAP_MAX_BOTH = 0.6     # ...and together in at most this share of the lists chance would give
WITH_PHI = 0.30         # pairs at least this linked are "go together"
SLOT_RATIO = 0.6        # merge two groups while Var(A + B) / (Var(A) + Var(B)) stays below this
SLOT_MAX = 5            # cards per slot
SLOT_STEADY = 0.8       # share of lists within one card of the slot's usual total
SLOT_MIN_COVER_OTHER = 0.25  # at most this share of lists may fill a slot in an unlisted way
MIN_WIN_MATCHES = 30    # win rates on fewer matches are not shown
MU_MIN_MATCHES = 10     # matches each side needs against an opponent to compare it
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
TREE_DEPTH = 3
TREE_MIN_SHARE = 0.07
TREE_MIN_LISTS = 15
TREE_MIN_GAIN = 0.04    # share of the node's spread a split must explain


def wilson(w, n):
    return analysis.wilson(w, n) if n > 0 else (None, None)


def r(x, d=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


class Records:
    """Per-list non-mirror record and pilot lift, to give any set of lists a win rate."""

    def __init__(self, matches: pd.DataFrame, pilot: ratings.PilotFit):
        nm = analysis.non_mirror(matches).dropna(subset=["deck_id"])
        codes = nm.groupby("deck_id", sort=True).ngroup().to_numpy()
        lift, _ = pilot.sums(nm.index, codes, codes.max() + 1)
        g = nm.groupby("deck_id", sort=True).agg(w=("score", "sum"), n=("score", "size"))
        g["lift"] = lift
        self.t = g
        # The same per list and opponent, for matchups (opponents with a known list only).
        known = nm[nm["opp_archetype"] != UNKNOWN]
        keys = ["deck_id", "opp_archetype"]
        codes = known.groupby(keys, sort=True).ngroup().to_numpy()
        lift, _ = pilot.sums(known.index, codes, codes.max() + 1)
        mu = known.groupby(keys, sort=True).agg(w=("score", "sum"), n=("score", "size"))
        mu["lift"] = lift
        self.mu = mu.reset_index()

    def vs(self, a, b, top: int = 3) -> list:
        """Per opponent: lists `a` against lists `b`, pilot-adjusted, with a Newcombe interval.

        Only opponents both sides met MU_MIN_MATCHES+ times. Returns the `top` opponents each
        way, ranked by how far the difference is from zero relative to its interval, as
        [opponent, diff, lo, hi, matches a, win rate a, matches b, win rate b, raw rate a, raw rate b]
        (raw rates let the page recompute the interval at another level).
        """
        def per_opp(ids):
            sub = self.mu[self.mu["deck_id"].isin(set(ids))]
            return sub.groupby("opp_archetype")[["w", "n", "lift"]].sum()
        A, B = per_opp(a), per_opp(b)
        j = A.join(B, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j["n_a"] >= MU_MIN_MATCHES) & (j["n_b"] >= MU_MIN_MATCHES)]
        rows = []
        for opp, x in j.iterrows():
            ra, rb = x.w_a / x.n_a, x.w_b / x.n_b
            aa, ab = ra - x.lift_a / x.n_a, rb - x.lift_b / x.n_b
            lo, hi = analysis.newcombe(x.w_a, x.n_a, x.w_b, x.n_b)
            shift = (aa - ra) - (ab - rb)
            d = aa - ab
            z = d / max((hi - lo) / (2 * analysis.Z), 1e-9)
            rows.append((z, [opp, r(d), r(lo + shift), r(hi + shift), int(x.n_a), r(aa), int(x.n_b), r(ab), r(ra), r(rb)]))
        rows.sort(key=lambda t: -t[0])
        better = [x for z, x in rows if x[1] > 0][:top]
        worse = [x for z, x in reversed(rows) if x[1] < 0][:top]
        return better + worse

    def of(self, ids) -> dict:
        s = self.t.reindex(list(ids)).dropna()
        w, n, lift = float(s["w"].sum()), int(s["n"].sum()), float(s["lift"].sum())
        if n == 0:
            return {"lists": len(s), "n": 0}
        lo, hi = wilson(w, n)
        raw = w / n
        adj = raw - lift / n
        return {"lists": int(len(s)), "w": r(w, 1), "n": n, "raw": r(raw), "wr": r(adj),
                "lo": r(lo - raw + adj), "hi": r(hi - raw + adj)}

    def diff(self, a, b) -> dict | None:
        """Win rate of lists `a` minus lists `b`, pilot-adjusted, Newcombe interval."""
        A, B = self.of(a), self.of(b)
        if not A.get("n") or not B.get("n"):
            return None
        lo, hi = analysis.newcombe(A["w"], A["n"], B["w"], B["n"])
        shift = (A["wr"] - A["raw"]) - (B["wr"] - B["raw"])
        d = A["wr"] - B["wr"]
        return {"a": A, "b": B, "d": r(d), "lo": r(lo + shift), "hi": r(hi + shift)}


def aggregate_list(X: pd.DataFrame, size: int) -> list:
    """Frank Karsten's aggregate decklist: the `size` most common (card, nth copy) pairs."""
    entries = []
    for card in X.columns:
        col = X[card].to_numpy()
        for k in range(1, int(col.max()) + 1):
            entries.append(((col >= k).mean(), card, k))
    entries.sort(key=lambda e: -e[0])
    counts: dict[str, int] = {}
    for share, card, k in entries[:size]:
        counts[card] = max(counts.get(card, 0), k)
    return sorted(([c, n] for c, n in counts.items()), key=lambda x: (-x[1], x[0]))


def options(col: np.ndarray, min_share: float = 0.03) -> list:
    """[copies, share of lists] for every copy count in 3%+ of the lists, most common first."""
    vals, cnt = np.unique(col.astype(int), return_counts=True)
    share = cnt / max(len(col), 1)
    return [[int(v), r(s)] for v, s in sorted(zip(vals, share), key=lambda x: -x[1]) if s >= min_share]


def copy_dist(col: np.ndarray) -> list:
    """Share of lists with 0, 1, 2, 3, 4+ copies."""
    c = np.clip(col, 0, 4).astype(int)
    return [r((c == k).mean()) for k in range(5)]


# ---------------------------------------------------------------- tiers
def tiers(X: pd.DataFrame) -> dict:
    play = (X > 0).mean()
    mean = X.mean()
    out = {"core": [], "flex": [], "spice": []}
    for card in X.columns:
        col = X[card].to_numpy()
        p = play[card]
        nz = col[col > 0]
        mode = int(pd.Series(nz).mode().iat[0]) if len(nz) else 0
        mode_share = float((nz == mode).mean()) if len(nz) else 0
        row = {"card": card, "play": r(p), "mean": r(mean[card], 2), "mode": mode, "modeShare": r(mode_share),
               "dist": copy_dist(col), "opts": options(col), "played": options(nz, 0.05)}
        if p >= CORE_PLAY:
            # Nearly everyone plays it; the decision, if any, is how many.
            row["countDecision"] = bool((col == options(col)[0][0]).mean() < 0.75)
            out["core"].append(row)
        elif p >= FLEX_MIN_PLAY and (col > 0).sum() >= MIN_CARD_LISTS:
            out["flex"].append(row)
        elif (col > 0).sum() >= 3:
            out["spice"].append(row)
    for k in out:
        out[k].sort(key=lambda x: (-x["play"], -x["mean"]))
    out["coreCopies"] = r(sum(x["mean"] * x["play"] for x in out["core"]), 1)
    return out


def variable(X: pd.DataFrame, t: dict) -> list[str]:
    """Cards that carry decisions: flex cards plus core cards whose copy count varies."""
    names = [x["card"] for x in t["flex"]] + [x["card"] for x in t["core"] if x["countDecision"]]
    return [c for c in names if X[c].std() > 0]


def merge_groups(S: dict, cards: list[str]) -> list[list[str]]:
    """Greedily merge the two groups of cards that trade off the most: whose summed copies
    vary least compared with each on its own. Basic lands trade off with everything
    (every list has 60 cards), so they stay out."""
    groups = [[c] for c in cards if c not in BASICS]

    def total(g):
        return sum(S[c] for c in g)

    def ratio_pair(a, b):
        va, vb = total(a).var(), total(b).var()
        return (total(a) + total(b)).var() / (va + vb) if va + vb > 0 else 1.0

    while True:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if len(groups[i]) + len(groups[j]) > SLOT_MAX:
                    continue
                rt = ratio_pair(groups[i], groups[j])
                if rt < SLOT_RATIO and (best is None or rt < best[0]):
                    best = (rt, i, j)
        if best is None:
            return groups
        _, i, j = best
        groups[i] = groups[i] + groups[j]
        del groups[j]


# ---------------------------------------------------------------- idea A
def idea_a(X: pd.DataFrame, cards: list[str], rec: Records, t: dict) -> dict:
    ids = X.index
    inout = [c for c in cards if (X[c] > 0).mean() < CORE_PLAY]
    P = (X[inout] > 0)
    n = len(X)
    pairs = []
    # Swaps and packages compare "plays it" with "doesn't", which only makes sense for
    # cards that a real share of lists leave out.
    for i, a in enumerate(inout):
        for b in inout[i + 1:]:
            pa, pb = P[a].to_numpy(), P[b].to_numpy()
            both, oa, ob = (pa & pb).sum(), (pa & ~pb).sum(), (~pa & pb).sum()
            neither = n - both - oa - ob
            den = math.sqrt(pa.mean() * (1 - pa.mean()) * pb.mean() * (1 - pb.mean()))
            if den == 0:
                continue
            phi = ((both * neither) - (oa * ob)) / (n * n) / den
            corr = float(np.corrcoef(X[a], X[b])[0, 1])
            pair = {"a": a, "b": b, "phi": r(phi), "corr": r(corr), "both": int(both), "onlyA": int(oa),
                    "onlyB": int(ob), "neither": int(neither), "expBoth": r(pa.mean() * pb.mean() * n, 1)}
            if phi <= SWAP_PHI and oa >= 5 and ob >= 5 and both <= SWAP_MAX_BOTH * pa.mean() * pb.mean() * n:
                pair["kind"] = "swap"
                pair["win"] = rec.diff(ids[pa & ~pb], ids[~pa & pb])
            elif phi >= WITH_PHI and both >= 5:
                pair["kind"] = "with"
            else:
                continue
            pairs.append(pair)
    pairs.sort(key=lambda p: p["phi"])

    # Slots: greedily merge the two groups that trade off the most, i.e. whose summed copies
    # vary least compared with each on its own. Basic lands trade off with everything
    # (every list has 60 cards), so they stay out.
    S = {c: X[c].to_numpy(dtype=float) for c in cards}
    groups = merge_groups(S, cards)

    def ratio(g):
        vp = sum(S[c].var() for c in g)
        return sum(S[c] for c in g).var() / vp if vp > 0 else 1.0

    slots = []
    for g in groups:
        if len(g) < 2:
            continue
        tot = sum(S[c] for c in g)
        vals, cnt = np.unique(tot, return_counts=True)
        mode = vals[cnt.argmax()]
        # A slot must hold a steady number of cards; otherwise it's just loosely related cards.
        if (np.abs(tot - mode) <= 1).mean() < SLOT_STEADY:
            continue
        members = sorted(({"card": c, "mean": r(S[c].mean(), 2), "play": r((S[c] > 0).mean()),
                           "dist": copy_dist(S[c])} for c in g), key=lambda m: -m["mean"])
        # Win rate by which card fills most of the slot.
        lead = np.array(g)[np.argmax(np.column_stack([S[c] for c in g]), axis=1)]
        by_lead = []
        for c in [m["card"] for m in members]:
            sel = ids[lead == c]
            if len(sel) >= 5:
                by_lead.append({"card": c, "lists": int(len(sel)), "win": rec.of(sel)})
        # The concrete ways lists fill the slot, most common first.
        names = [m["card"] for m in members]
        combo = pd.Series(list(map(tuple, np.column_stack([S[c] for c in names]).astype(int))), index=ids)
        configs = []
        for key, cnt in combo.value_counts().items():
            if cnt / n < 0.03 or len(configs) >= 6:
                break
            sel = ids[(combo == key).to_numpy()]
            configs.append({"counts": [int(v) for v in key], "lists": int(cnt), "share": r(cnt / n),
                            "win": rec.of(sel) if cnt >= 10 else None})
        other = n - sum(c["lists"] for c in configs)
        if other / n > SLOT_MIN_COVER_OTHER:
            continue  # no typical way to fill it: loosely related cards, not a slot
        slots.append({"cards": members, "total": r(tot.mean(), 1), "mode": int(mode), "configs": configs,
                      "otherLists": int(other), "totals": options(tot),
                      "modeShare": r((tot == mode).mean()), "nearMode": r((np.abs(tot - mode) <= 1).mean()),
                      "ratio": r(ratio(g)), "byLead": by_lead})
    slots.sort(key=lambda s: -s["total"])

    # Correlation matrix of copy counts, ordered by hierarchical clustering.
    order = cards
    corr = np.corrcoef(X[cards].to_numpy(dtype=float).T) if len(cards) > 1 else np.ones((1, 1))
    corr = np.nan_to_num(corr)
    if len(cards) > 2:
        dist = np.clip(1 - corr, 0, 2)
        np.fill_diagonal(dist, 0)
        order = [cards[i] for i in leaves_list(linkage(squareform(dist, checks=False), "average"))]
    pos = {c: i for i, c in enumerate(cards)}
    mat = [[r(corr[pos[a], pos[b]], 2) for b in order] for a in order]
    return {"pairs": pairs, "slots": slots, "matrix": {"cards": order, "corr": mat}}


# ---------------------------------------------------------------- decisions within a group of lists
def decisions(X: pd.DataFrame, rows: np.ndarray, rec: Records, detail: bool = False) -> dict:
    """What the lists in `rows` (one shell, or the whole deck) agree on and where they differ.

    cards: per card played by 3%+ of these lists, the copy counts and their shares.
    slots: groups of cards that replace each other in these lists, with the ways they're filled.
    Each decision carries a win-rate difference between its two main options.
    """
    sub = X.iloc[rows]
    ids = sub.index
    n = len(sub)
    cards = {}
    for c in sub.columns:
        col = sub[c].to_numpy()
        play = (col > 0).mean()
        if play < 0.03:
            continue
        opts = options(col, 0.03)
        entry = {"opts": opts, "play": r(play)}
        top = opts[0]
        if play >= CORE_PLAY and top[1] < CORE_PLAY:
            hi_lo = [o[0] for o in opts if o[0] > 0][:2]
            if len(hi_lo) == 2:
                hi, lo = max(hi_lo), min(hi_lo)
                entry["win"] = rec.diff(ids[col == hi], ids[col == lo])
                entry["winLabel"] = [hi, lo]
        elif FLEX_MIN_PLAY <= play < CORE_PLAY and (col > 0).sum() >= MIN_CARD_LISTS and (col == 0).sum() >= MIN_CARD_LISTS:
            entry["win"] = rec.diff(ids[col > 0], ids[col == 0])
        if detail and top[1] < CORE_PLAY and play >= FLEX_MIN_PLAY:
            # Every option on its own: how often, win rate, and matchups against the other lists.
            if play >= CORE_PLAY:
                sides = [(str(k), col == k) for k, share in opts if share >= 0.05]
            else:
                sides = [("yes", col > 0), ("no", col == 0)]
            entry["sides"] = [{"label": lab, "share": r(m.mean()), "win": rec.of(ids[m]), "mu": rec.vs(ids[m], ids[~m])}
                              for lab, m in sides]
        cards[c] = entry
    # Slots within these lists: cards that vary here and replace each other.
    varying = [c for c, v in cards.items() if v["opts"][0][1] < CORE_PLAY and v["play"] >= FLEX_MIN_PLAY]
    S = {c: sub[c].to_numpy(dtype=float) for c in varying}
    slot_out = []
    for g in merge_groups(S, varying):
        if len(g) < 2:
            continue
        tot = sum(S[c] for c in g)
        vals, cnt = np.unique(tot, return_counts=True)
        mode = vals[cnt.argmax()]
        if (np.abs(tot - mode) <= 1).mean() < SLOT_STEADY:
            continue
        names = sorted(g, key=lambda c: -S[c].mean())
        combo = pd.Series(list(map(tuple, np.column_stack([S[c] for c in names]).astype(int))), index=ids)
        vc = combo.value_counts()
        if 1 - vc[vc / n >= 0.03].iloc[:6].sum() / n > SLOT_MIN_COVER_OTHER:
            continue
        configs = []
        for key, k in vc.items():
            if k / n < 0.05 or len(configs) >= 4:
                break
            sel = ids[(combo == key).to_numpy()]
            cfg = {"counts": [int(v) for v in key], "share": r(k / n), "lists": int(k), "win": rec.of(sel)}
            if detail:
                cfg["mu"] = rec.vs(sel, ids[~(combo == key).to_numpy()])
            configs.append(cfg)
        slot_out.append({"cards": names, "configs": configs, "total": int(mode),
                         "other": r(1 - sum(c["share"] for c in configs))})
    return {"cards": cards, "slots": slot_out, "lists": n}


# ---------------------------------------------------------------- shells (question tree)
def idea_c(X: pd.DataFrame, cards: list[str], rec: Records, size: int) -> dict:
    n_all = len(X)
    min_n = max(TREE_MIN_LISTS, int(TREE_MIN_SHARE * n_all))
    M = X.to_numpy(dtype=float)
    col = {c: i for i, c in enumerate(X.columns)}
    agg_all = dict(aggregate_list(X, size))

    def sse(rows, skip):
        sub = M[rows]
        s = ((sub - sub.mean(axis=0)) ** 2).sum(axis=0)
        return s.sum() - s[skip]

    def node(rows: np.ndarray, depth: int, path: list) -> dict:
        ids = X.index[rows]
        sub = X.iloc[rows]
        agg = aggregate_list(sub, size)
        out = {"lists": int(rows.sum()), "share": r(rows.sum() / n_all), "path": path,
               "win": rec.of(ids), "list": agg,
               "vsAll": sorted(([c, k - agg_all.get(c, 0)] for c, k in agg if k != agg_all.get(c, 0)),
                               key=lambda x: -abs(x[1]))
                        + [[c, -k] for c, k in agg_all.items() if c not in dict(agg)]}
        if depth == 0:
            out["dec"] = decisions(X, rows, rec, detail=True)
        if depth >= TREE_DEPTH or rows.sum() < 2 * min_n:
            out["dec"] = decisions(X, rows, rec, detail=depth == 0)
            if depth > 0:
                out["mu"] = rec.vs(ids, X.index[~rows])
            return out
        best = None
        for c in cards:
            j = col[c]
            base = sse(rows, j)
            if base <= 0:
                continue
            v = M[:, j]
            for k in range(1, int(v[rows].max()) + 1):
                right = rows & (v >= k)
                left = rows & (v < k)
                if right.sum() < min_n or left.sum() < min_n:
                    continue
                gain = (base - sse(left, j) - sse(right, j)) / base
                if best is None or gain > best[0]:
                    best = (gain, c, k, left, right)
        if best is None or best[0] < TREE_MIN_GAIN:
            out["dec"] = decisions(X, rows, rec, detail=depth == 0)
            if depth > 0:
                out["mu"] = rec.vs(ids, X.index[~rows])
            return out
        gain, c, k, left, right = best
        ml, mr = M[left].mean(axis=0), M[right].mean(axis=0)
        delta = mr - ml
        top = np.argsort(-np.abs(delta))
        def side(sel, i):
            v = M[sel, i]
            nz = v[v > 0]
            return {"play": r((v > 0).mean()), "opts": options(nz, 0.15)[:2]}
        moves = [{"card": X.columns[i], "yes": side(right, i), "no": side(left, i)}
                 for i in top if X.columns[i] != c and abs(delta[i]) >= 0.5][:8]
        q = f"{k}+ {c}" if k > 1 else c
        out.update({"card": c, "k": k, "gain": r(gain), "moves": moves, "kind": "count" if (M[rows, col[c]] > 0).mean() >= CORE_PLAY else "inout",
                    "split": side(right, col[c]), "rest": side(left, col[c]),
                    "diff": rec.diff(X.index[right], X.index[left]),
                    "yes": node(right, depth + 1, path + [[c, k, True]]),
                    "no": node(left, depth + 1, path + [[c, k, False]])})
        return out

    return node(np.ones(n_all, bool), 0, [])


# ---------------------------------------------------------------- main
def board_block(Xb: pd.DataFrame, rec: Records, size: int) -> dict:
    t = tiers(Xb)
    cards = variable(Xb, t)
    block = {"tiers": t, "nVariable": len(cards), "flexSlots": r(size - (t["coreCopies"] or 0), 1)}
    if len(cards) >= 2:
        block["A"] = idea_a(Xb, cards, rec, t)
        block["C"] = idea_c(Xb, cards, rec, size)
    ids = Xb.index
    # In/out cards: lists with it against lists without it (as on the dashboard).
    block["cardWin"] = {c: rec.diff(ids[Xb[c] > 0], ids[Xb[c] == 0]) for c in cards
                        if (Xb[c] > 0).mean() < CORE_PLAY and 0 < (Xb[c] > 0).sum() < len(Xb)}
    # Copy-count decisions: lists with the more common higher count against the lower one (19 vs 18 Mountain).
    block["countWin"] = {}
    for x in t["core"]:
        if not x["countDecision"]:
            continue
        top = [o[0] for o in x["opts"] if o[0] > 0][:2]
        if len(top) == 2:
            hi, lo = max(top), min(top)
            col = Xb[x["card"]].to_numpy()
            block["countWin"][x["card"]] = {"hi": hi, "lo": lo, "win": rec.diff(ids[col == hi], ids[col == lo])}
    return block


def main() -> None:
    tables = pd.read_pickle(ROOT / "data" / "processed" / "tables.pkl")
    end = tables["decks"]["date"].max().normalize()
    since = end - pd.Timedelta(days=DAYS - 1)
    tab = analysis.filter_period(tables, since=since.date().isoformat(), until=end.date().isoformat())
    print("fitting pilot ratings ...")
    pilot = ratings.fit_scope(tables, None, end, keep_since=since, bootstrap=0)
    rec = Records(tab["matches"], pilot)
    decks = tab["decks"]
    counts = decks["archetype"].value_counts()
    names = [a for a in counts.index if a != "Unknown" and counts[a] >= MIN_LISTS][:N_ARCHETYPES]
    colors = decks.groupby("archetype")["color"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else "")
    dc = tab["deck_cards"]
    out = []
    for name in names:
        d = decks[decks["archetype"] == name].set_index("deck_id")
        sub = dc[dc["deck_id"].isin(set(d.index))]
        entry = {"name": name, "color": colors[name], "lists": int(len(d)),
                 "withMatches": int(rec.t.index.isin(d.index).sum()), "win": rec.of(d.index), "boards": {}}
        for board, size in (("main", 60), ("side", 15)):
            Xb = sub[sub["board"] == board].pivot_table(index="deck_id", columns="card", values="count",
                                                        aggfunc="sum", fill_value=0)
            Xb = Xb.reindex(d.index, fill_value=0)
            # Snow-covered basics are a cosmetic choice: count them as the basic.
            for c in [c for c in Xb.columns if c.startswith("Snow-Covered ")]:
                base = c.removeprefix("Snow-Covered ")
                Xb[base] = Xb.get(base, 0) + Xb.pop(c)
            Xb = Xb.loc[:, (Xb > 0).sum() >= 3]
            entry["boards"][board] = board_block(Xb, rec, size)
        out.append(entry)
        print(f"{name}: {len(d)} lists")
    meta = {"since": since.date().isoformat(), "until": end.date().isoformat(), "days": DAYS,
            "settings": {"corePlay": CORE_PLAY, "flexMinPlay": FLEX_MIN_PLAY, "swapPhi": SWAP_PHI, "swapMaxBoth": SWAP_MAX_BOTH,
                         "withPhi": WITH_PHI, "slotRatio": SLOT_RATIO, "slotSteady": SLOT_STEADY, "slotOther": SLOT_MIN_COVER_OTHER, "minWinMatches": MIN_WIN_MATCHES, "muMinMatches": MU_MIN_MATCHES, "treeDepth": TREE_DEPTH,
                         "treeMinShare": TREE_MIN_SHARE, "treeMinGain": TREE_MIN_GAIN}}
    OUT.write_text("window.DATA = " + json.dumps({"meta": meta, "decks": out}, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
