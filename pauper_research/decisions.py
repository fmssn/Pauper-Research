"""Builds and deckbuilding decisions within one archetype.

Each list of a deck is a vector of copy counts. Per archetype and board:

- **Builds:** a divisive tree of single-card questions ("4+ Moon-Circuit Hacker?"),
  each the card choice that best predicts the rest of the list. The leaves are the
  builds; each gets a typical list (Frank Karsten's aggregate decklist).
- **Decisions** (within the whole deck, and within each build): fixed cards,
  copy-count decisions ("18 or 19 Mountain"), in/out cards, and slots: groups of
  cards whose combined copies vary much less than each alone, shown as the actual
  splits lists use.

Every option carries the raw record of its lists, their average pilot lift and the
bootstrap SD of that lift, so the page can show raw or pilot-adjusted win rates the
same way it does everywhere else. Options can also carry the opponents they do
best and worst against compared with the deck's other lists.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import sparse

from . import analysis
from .archetypes import UNKNOWN

MIN_LISTS = 80            # lists an archetype needs before it gets builds and decisions
CORE_PLAY = 0.85          # one copy count in this share of lists: the card is fixed
MIN_OPTION_SHARE = 0.05   # options (copy counts, slot splits) shown when in this share of lists
MAX_SLOT_OPTIONS = 4      # slot splits shown
SLOT_RATIO = 0.6          # merge two card groups while Var(A + B) / (Var A + Var B) stays below this
SLOT_MAX = 5              # cards per slot
SLOT_STEADY = 0.8         # share of lists within one card of the slot's usual total
SLOT_MIN_COVER = 0.75     # share of lists its listed splits must cover
TREE_DEPTH = 3            # questions asked at most
TREE_MIN_SHARE = 0.07     # share of the deck's lists each side of a question needs...
TREE_MIN_LISTS = 15       # ...and at least this many lists
TREE_MIN_GAIN = 0.04      # share of the remaining spread a question must explain
MU_MIN_MATCHES = 30       # matches each side needs against an opponent to compare it
MU_TOP = 3                # opponents shown each way per option
BASICS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
SIZES = {"main": 60, "side": 15}


def _r(x, d: int = 4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), d)


def _w(x: float):
    x = float(x)
    return int(x) if x.is_integer() else round(x, 1)


def _sd(boot: np.ndarray | None) -> float:
    return float(boot.std(ddof=1)) if boot is not None and len(boot) >= 2 else 0.0


class Records:
    """Each list's non-mirror record and pilot lift (with its bootstrap replicates), so any
    set of lists gets a win rate, and per opponent for matchups."""

    def __init__(self, matches: pd.DataFrame, pilot):
        nm = analysis.non_mirror(matches).dropna(subset=["deck_id"])
        self.t, self.boot = self._table(nm, ["deck_id"], pilot)
        known = nm[nm["opp_archetype"] != UNKNOWN]
        mu, self.mu_boot = self._table(known, ["deck_id", "opp_archetype"], pilot)
        self.mu = mu.reset_index()
        self.row = pd.Series(np.arange(len(self.t)), index=self.t.index)

    @staticmethod
    def _table(nm: pd.DataFrame, keys: list[str], pilot):
        g = nm.groupby(keys, sort=True).agg(w=("score", "sum"), n=("score", "size"))
        g["lift"] = 0.0
        boot = None
        if pilot is not None and len(g):
            codes = nm.groupby(keys, sort=True).ngroup().to_numpy()
            g["lift"], boot = pilot.sums(nm.index, codes, len(g))
        return g, boot

    def _sum(self, ids) -> tuple[float, int, float, np.ndarray | None]:
        pos = self.row.reindex(list(ids)).dropna().to_numpy(dtype=int)
        s = self.t.iloc[pos]
        boot = self.boot[pos].sum(axis=0) if self.boot is not None else None
        return float(s["w"].sum()), int(s["n"].sum()), float(s["lift"].sum()), boot

    def of(self, ids) -> list | None:
        """[wins, matches, average lift, SD of the average lift], or None without matches."""
        w, n, lift, boot = self._sum(ids)
        if n == 0:
            return None
        return [_w(w), n, _r(lift / n), _r(_sd(None if boot is None else boot / n))]

    def diff(self, a, b) -> list | None:
        """Lists `a` against lists `b`: [wins a, matches a, lift a, wins b, matches b, lift b,
        SD of the lift difference], as the dashboard's card comparisons."""
        wa, na, la, ba = self._sum(a)
        wb, nb, lb, bb = self._sum(b)
        if not na or not nb:
            return None
        sd = _sd(None if ba is None else ba / na - bb / nb)
        return [_w(wa), na, _r(la / na), _w(wb), nb, _r(lb / nb), _r(sd)]

    def vs(self, a, b, opp_index: dict[str, int]) -> list:
        """Per opponent, lists `a` against lists `b`, for opponents both met MU_MIN_MATCHES+ times.

        Keeps the MU_TOP opponents each way, ranked by how far the pilot-adjusted
        difference is from zero relative to its 95% interval. Entries are
        [opponent index, wins a, matches a, lift a, wins b, matches b, lift b, SD].
        """
        sides = []
        for ids in (a, b):
            mask = self.mu["deck_id"].isin(set(ids)).to_numpy()
            sub = self.mu[mask]
            codes, opps = pd.factorize(sub["opp_archetype"], sort=True)
            agg = sub.groupby(codes)[["w", "n", "lift"]].sum()
            agg.index = opps[agg.index]
            boot = None
            if self.mu_boot is not None and mask.any():
                ind = sparse.csr_matrix((np.ones(mask.sum()), (codes, np.arange(mask.sum()))), shape=(len(opps), mask.sum()))
                boot = pd.DataFrame(np.asarray(ind @ self.mu_boot[mask]), index=opps)
            sides.append((agg, boot))
        (A, bA), (B, bB) = sides
        j = A.join(B, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j["n_a"] >= MU_MIN_MATCHES) & (j["n_b"] >= MU_MIN_MATCHES) & j.index.isin(list(opp_index))]
        rows = []
        for opp, x in j.iterrows():
            la, lb = x.lift_a / x.n_a, x.lift_b / x.n_b
            sd = _sd(None if bA is None else bA.loc[opp].to_numpy() / x.n_a - bB.loc[opp].to_numpy() / x.n_b)
            d = x.w_a / x.n_a - x.w_b / x.n_b - (la - lb)
            lo, hi = analysis.newcombe(x.w_a, x.n_a, x.w_b, x.n_b)
            half = math.hypot((hi - lo) / 2, analysis.Z * sd)
            rows.append((d / max(half, 1e-9), [opp_index[opp], _w(x.w_a), int(x.n_a), _r(la), _w(x.w_b), int(x.n_b), _r(lb), _r(sd)]))
        rows.sort(key=lambda t: -t[0])
        better = [e for z, e in rows if z > 0][:MU_TOP]
        worse = [e for z, e in reversed(rows) if z < 0][:MU_TOP]
        return better + worse


def aggregate_list(X: pd.DataFrame, size: int) -> list:
    """Frank Karsten's aggregate decklist: the `size` most common (card, nth copy) pairs."""
    entries = []
    for card in X.columns:
        col = X[card].to_numpy()
        for k in range(1, int(col.max()) + 1):
            entries.append(((col >= k).mean(), card, k))
    entries.sort(key=lambda e: (-e[0], e[1], e[2]))
    counts: dict[str, int] = {}
    for _, card, k in entries[:size]:
        counts[card] = max(counts.get(card, 0), k)
    return sorted(([c, n] for c, n in counts.items()), key=lambda x: (-x[1], x[0]))


def options(col: np.ndarray, min_share: float = 0.03) -> list:
    """[copies, share of lists] for every copy count in `min_share`+ of the lists, most common first."""
    vals, cnt = np.unique(col.astype(int), return_counts=True)
    share = cnt / max(len(col), 1)
    order = sorted(zip(vals, share), key=lambda x: (-x[1], x[0]))
    return [[int(v), _r(s, 3)] for v, s in order if s >= min_share]


def kind(col: np.ndarray) -> str:
    """fixed: one copy count (0 included) in CORE_PLAY+ of lists; count: nearly everyone
    plays it, in different numbers; inout: the rest."""
    _, cnt = np.unique(col.astype(int), return_counts=True)
    if cnt.max() / len(col) >= CORE_PLAY:
        return "fixed"
    return "count" if (col > 0).mean() >= CORE_PLAY else "inout"


def merge_groups(S: dict[str, np.ndarray], cards: list[str]) -> list[list[str]]:
    """Greedily merge the two groups of cards that trade off the most: whose summed copies
    vary least compared with each on its own. Basic lands trade off with everything
    (every list has 60 cards), so they stay out."""
    groups = [[c] for c in cards if c not in BASICS]
    totals = [S[c].copy() for c in cards if c not in BASICS]
    while True:
        best = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if len(groups[i]) + len(groups[j]) > SLOT_MAX:
                    continue
                va, vb = totals[i].var(), totals[j].var()
                ratio = (totals[i] + totals[j]).var() / (va + vb) if va + vb > 0 else 1.0
                if ratio < SLOT_RATIO and (best is None or ratio < best[0]):
                    best = (ratio, i, j)
        if best is None:
            return groups
        _, i, j = best
        groups[i] += groups.pop(j)
        totals[i] = totals[i] + totals.pop(j)


def decisions(X: pd.DataFrame, rows: np.ndarray, rec: Records, detail: bool = False,
              opp_index: dict[str, int] | None = None) -> dict:
    """What the lists in `rows` (one build, or the whole deck) agree on and where they differ.

    cards: {card: ["fixed", copies]} for cards every list plays the same, else
      {card: [kind, options, share of lists playing it, comparison, sides]}. The comparison
      is lists with the two most common counts against each other (copy-count decisions,
      as [more, fewer, comparison]) or lists with the card against lists without it
      (in/out). With `detail`, sides lists every option as [label, share, record,
      comparison with the other lists, matchups against them]; matchups (see
      `Records.vs`) need `opp_index`, else they are None.
    slots: groups of cards that replace each other here, with the ways lists fill them
      (with `detail`, each split as an option like the sides above).
    """
    sub = X.iloc[np.flatnonzero(rows)]
    ids, n = sub.index, len(sub)

    def option(label, share, mask, mu=True):
        """An option against the other lists of the group: record, comparison, matchups."""
        a, b = ids[mask], ids[~mask]
        return [label, _r(share, 3), rec.of(a), rec.diff(a, b),
                rec.vs(a, b, opp_index) if mu and opp_index is not None else None]

    cards = {}
    for c in sub.columns:
        col = sub[c].to_numpy()
        play = (col > 0).mean()
        if play < 0.03:
            continue
        k, opts = kind(col), options(col, MIN_OPTION_SHARE)
        if k == "fixed":
            if opts[0][0] > 0:
                cards[c] = [k, opts[0][0]]
            continue
        cmp = sides = None
        if k == "count":
            top = sorted(o[0] for o in opts if o[0] > 0)[-2:] if len(opts) > 1 else []
            if len(top) == 2:
                cmp = [top[1], top[0], rec.diff(ids[col == top[1]], ids[col == top[0]])]
            if detail:
                sides = [option(str(v), s, col == v) for v, s in opts]
        else:
            cmp = rec.diff(ids[col > 0], ids[col == 0])
            if detail:
                # Matchups once, on the "yes" row: with it against without it.
                sides = [option("yes", play, col > 0), option("no", 1 - play, col == 0, mu=False)]
        cards[c] = [k, opts, _r(play, 3), cmp, sides]

    varying = [c for c, v in cards.items() if v[0] != "fixed"]
    S = {c: sub[c].to_numpy(dtype=float) for c in varying}
    slots = []
    for g in merge_groups(S, varying):
        if len(g) < 2:
            continue
        tot = sum(S[c] for c in g)
        vals, cnt = np.unique(tot, return_counts=True)
        mode = vals[cnt.argmax()]
        # A slot holds a steady number of cards; otherwise it's just loosely related cards.
        if (np.abs(tot - mode) <= 1).mean() < SLOT_STEADY:
            continue
        names = sorted(g, key=lambda c: (-S[c].mean(), c))
        combo = pd.Series(list(map(tuple, np.column_stack([S[c] for c in names]).astype(int))), index=ids)
        vc = combo.value_counts()
        shown = vc[vc / n >= MIN_OPTION_SHARE].iloc[:MAX_SLOT_OPTIONS]
        if shown.sum() / n < SLOT_MIN_COVER:
            continue
        masks = [(combo == key).to_numpy() for key in shown.index]
        configs = [option([int(v) for v in key], m.mean(), m) if detail else [[int(v) for v in key], _r(m.mean(), 3)]
                   for key, m in zip(shown.index, masks)]
        slot = {"cards": names, "total": int(mode), "configs": configs, "other": _r(1 - shown.sum() / n, 3)}
        if len(masks) > 1:
            slot["cmp"] = rec.diff(ids[masks[0]], ids[masks[1]])
        slots.append(slot)
    return {"cards": cards, "slots": slots}


def builds(X: pd.DataFrame, rec: Records, size: int, opp_index: dict[str, int] | None) -> list:
    """The leaves of the question tree, largest first, each with its typical list and decisions."""
    n_all = len(X)
    min_n = max(TREE_MIN_LISTS, int(TREE_MIN_SHARE * n_all))
    M = X.to_numpy(dtype=float)
    leaves = []

    def sse(rows: np.ndarray, skip: int) -> float:
        sub = M[rows]
        s = ((sub - sub.mean(axis=0)) ** 2).sum(axis=0)
        return s.sum() - s[skip]

    def node(rows: np.ndarray, depth: int, path: list) -> None:
        best = None
        if depth < TREE_DEPTH and rows.sum() >= 2 * min_n:
            for j, c in enumerate(X.columns):
                v = M[:, j]
                if v[rows].min() == v[rows].max():
                    continue
                base = sse(rows, j)
                if base <= 0:
                    continue
                for k in range(int(v[rows].min()) + 1, int(v[rows].max()) + 1):
                    right, left = rows & (v >= k), rows & (v < k)
                    if right.sum() < min_n or left.sum() < min_n:
                        continue
                    gain = (base - sse(left, j) - sse(right, j)) / base
                    if best is None or gain > best[0]:
                        best = (gain, c, k, left, right)
        if best is None or best[0] < TREE_MIN_GAIN:
            ids = X.index[rows]
            leaf = {"path": path, "lists": int(rows.sum()), "share": _r(rows.sum() / n_all, 3),
                    "win": rec.of(ids), "list": aggregate_list(X.iloc[np.flatnonzero(rows)], size),
                    "dec": decisions(X, rows, rec)}
            if path:
                leaf["cmp"] = rec.diff(ids, X.index[~rows])
                if opp_index is not None:
                    leaf["mu"] = rec.vs(ids, X.index[~rows], opp_index)
            leaves.append(leaf)
            return
        _, c, k, left, right = best
        node(right, depth + 1, path + [[c, k, 1]])
        node(left, depth + 1, path + [[c, k, 0]])

    node(np.ones(n_all, bool), 0, [])
    leaves.sort(key=lambda x: -x["lists"])
    return leaves


def name_builds(leaves: list) -> None:
    """Name builds by how they differ from the largest one, the stock list.

    A build is named after the cards its questions ask about, as it plays them: the first
    it plays more of than the stock list ("Moon-Circuit Hacker build"), else the first it
    plays fewer of ("No Fireblast build", "14 Island build"). When that name is taken, its
    other question cards qualify it ("…, 2 Chain Lightning"). Only a build whose question
    cards all match the stock list is named after the card it plays most more of.
    """
    if len(leaves) == 1:
        leaves[0]["name"] = "One build"
        return
    stock = dict(leaves[0]["list"])
    leaves[0]["name"] = "Stock list"
    names = {"Stock list"}
    for i, leaf in enumerate(leaves[1:], start=2):
        own = dict(leaf["list"])
        diffs = [(c, own.get(c, 0)) for c in dict.fromkeys(p[0] for p in leaf["path"]) if own.get(c, 0) != stock.get(c, 0)]
        lead = next(((c, k) for c, k in diffs if k > stock.get(c, 0)), diffs[0] if diffs else None)
        if lead is None:
            more = sorted((c for c in own if c not in BASICS and own[c] > stock.get(c, 0)), key=lambda c: (stock.get(c, 0) - own[c], c))
            lead = (more[0], own[more[0]]) if more else None
        if lead is None:
            name = "Build " + str(i)
        elif lead[1] > stock.get(lead[0], 0):
            name = lead[0] + " build"
        else:
            name = (f"{lead[1]} " if lead[1] else "No ") + lead[0] + " build"
        for c, k in diffs:
            if name not in names:
                break
            if lead is None or c != lead[0]:
                name += ", " + (f"{k} {c}" if k else "no " + c)
        k, unique = 2, name
        while unique in names:
            unique, k = f"{name} {k}", k + 1
        names.add(unique)
        leaf["name"] = unique


def card_matrix(deck_cards: pd.DataFrame, ids: pd.Index, board: str) -> pd.DataFrame:
    """Copies per list (rows) and card (columns). Snow-covered basics count as the basic."""
    sub = deck_cards[(deck_cards["board"] == board) & deck_cards["deck_id"].isin(set(ids))]
    card = sub["card"].where(~sub["card"].str.startswith("Snow-Covered "), sub["card"].str.removeprefix("Snow-Covered "))
    X = sub.assign(card=card).pivot_table(index="deck_id", columns="card", values="count", aggfunc="sum", fill_value=0)
    X = X.reindex(ids, fill_value=0)
    return X.loc[:, (X > 0).sum() >= 3]


def archetype(decks: pd.DataFrame, deck_cards: pd.DataFrame, name: str, rec: Records,
              opp_index: dict[str, int]) -> dict | None:
    """Builds and decisions of one archetype, per board, or None with fewer than MIN_LISTS lists.

    Matchups per option are left out on the sideboard: what a list sideboards
    depends on the field it expects, so they would mostly show that.
    """
    ids = pd.Index(decks.loc[decks["archetype"] == name, "deck_id"])
    if len(ids) < MIN_LISTS:
        return None
    out = {}
    for board, size in SIZES.items():
        X = card_matrix(deck_cards, ids, board)
        if X.empty:
            continue
        mu = opp_index if board == "main" else None
        ls = builds(X, rec, size, mu)
        everyone = np.ones(len(X), bool)
        overall = aggregate_list(X, size)
        name_builds(ls)
        out[board] = {"lists": len(X), "list": overall, "builds": ls, "dec": decisions(X, everyone, rec, True, mu)}
    return out
