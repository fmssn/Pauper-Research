"""Pilot skill: player ratings and how much they lift each deck's win rate.

Raw win rates mix two things: how good a deck is and how good its pilots are.
This module fits one model for both, a regularised Bradley-Terry model on
match results:

    logit P(win) = (player - opp_player) + (deck - opp_deck)

`deck` is an effect per archetype *per quarter* (decks get better or worse as
the meta moves), and `player` is a rating per player. Decks without a
published list get their own "Unknown" level. Player ratings are pulled
towards 0 by a ridge penalty whose strength is chosen by cross-validation,
so a player with a handful of matches stays close to average. Because the two
are fitted together, a player who always registers the best deck doesn't get
credit for the deck, and vice versa.

The fit uses the 12 months up to the end of the period being analysed, with
older matches down-weighted (half-life of 6 months), so ratings rest on more
than the period itself. Mirror matches are included: they are the cleanest
signal of skill, since the deck terms cancel out.

From the fit, every match gets a **pilot lift**: the model's win chance with
both players' ratings minus the win chance with both ratings set to 0. A
deck's pilot-adjusted win rate is its raw win rate minus its average lift,
over exactly the same matches. Bootstrap refits (resampling events) give the
uncertainty of the lift, which is added to the usual sampling interval.

Players are identified by their name, normalised (case, whitespace, Unicode)
and merged across sources. No player names leave this module's tables.

**Skill sensitivity.** The model above assumes a rating edge is worth the
same on every deck. To see where skill matters more, a second stage fits one
skill slope per archetype on the same window:

    logit P(win) = offset + b_a * r_i - b_b * r_j,    b_a = b0 + g_a

where `offset` is the fitted deck part, and `r` are *out-of-fold* ratings
(from the cross-validation fit that held out the match's event), so a
player's rating never comes from the match it is used to predict. The
deviations `g_a` get a ridge penalty, so decks with little data stay near
`b0`. A deck's sensitivity is its slope over the average slope of all decks
(weighted by matches, "Unknown" left out): 1 is average, above 1 means the
win rate rises and falls more with pilot skill.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse import linalg as splinalg

from .archetypes import UNKNOWN

LOOKBACK_DAYS = 365
HALF_LIFE_DAYS = 182.5
LAMBDA_GRID = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)  # player ridge penalty, ~ 1 / prior variance
DECK_LAMBDA = 1.0  # weak prior (SD 1 logit): keeps thin deck-quarters from running off
CV_FOLDS = 5
BOOTSTRAP = 100
SLOPE_LAMBDA = 4.0  # ridge on per-deck skill slopes (prior SD 0.5 around the average slope)
SKILL_MIN_MATCHES = 150  # matches in the window before a deck's skill sensitivity is reported


def normalize_name(name: object) -> str:
    """Player key: Unicode-normalised, trimmed, whitespace collapsed, lower case."""
    if not isinstance(name, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", name).split()).casefold()


def _keys(names: pd.Series) -> pd.Series:
    """`normalize_name` over a column, computed once per distinct name."""
    uniq = names.dropna().unique()
    return names.map(dict(zip(uniq, map(normalize_name, uniq)))).fillna("")


def _quarter(dates: pd.Series) -> pd.Series:
    return dates.dt.year.astype(str) + "Q" + dates.dt.quarter.astype(str)


@dataclass
class Design:
    """Sparse design for the matches in the fitting window (both sides of every match)."""
    X: sparse.csr_matrix   # columns: players, then deck-quarters
    y: np.ndarray
    w: np.ndarray          # recency weight
    event: np.ndarray      # event code per row, for grouped folds and the bootstrap
    n_players: int
    pi: np.ndarray         # player index of each side
    pj: np.ndarray
    ai: np.ndarray         # archetype code of each side (not per quarter)
    aj: np.ndarray
    archetypes: pd.Index


def _design(matches: pd.DataFrame, me: pd.Series, opp: pd.Series, end: pd.Timestamp, half_life: float) -> Design:
    players = pd.Index(pd.unique(pd.concat([me, opp], ignore_index=True)))
    q = _quarter(matches["date"])
    decks_me = matches["archetype"].astype(str) + "@" + q
    decks_opp = matches["opp_archetype"].astype(str) + "@" + q
    decks = pd.Index(pd.unique(pd.concat([decks_me, decks_opp], ignore_index=True)))
    n, n_p = len(matches), len(players)

    rows = np.repeat(np.arange(n), 4)
    cols = np.column_stack([players.get_indexer(me), players.get_indexer(opp),
                            n_p + decks.get_indexer(decks_me), n_p + decks.get_indexer(decks_opp)]).ravel()
    vals = np.tile([1.0, -1.0, 1.0, -1.0], n)
    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n, n_p + len(decks)))
    X.sum_duplicates()  # a mirror's deck columns cancel out to 0

    age = (end - matches["date"]).dt.days.clip(lower=0).to_numpy(dtype=float)
    w = np.power(0.5, age / half_life)
    event = pd.factorize(matches["event_id"])[0]
    archs = pd.Index(pd.unique(pd.concat([matches["archetype"], matches["opp_archetype"]], ignore_index=True).astype(str)))
    return Design(X, matches["score"].to_numpy(dtype=float), w, event, n_p,
                  players.get_indexer(me), players.get_indexer(opp),
                  archs.get_indexer(matches["archetype"].astype(str)),
                  archs.get_indexer(matches["opp_archetype"].astype(str)), archs)


def _rows(design: Design, mask: np.ndarray) -> Design:
    return Design(design.X[mask], design.y[mask], design.w[mask], design.event[mask], design.n_players,
                  design.pi[mask], design.pj[mask], design.ai[mask], design.aj[mask], design.archetypes)


def _penalty(design: Design, lam: float) -> np.ndarray:
    pen = np.full(design.X.shape[1], DECK_LAMBDA)
    pen[:design.n_players] = lam
    return pen


def _objective(X, y, weights, pen, theta) -> float:
    eta = X @ theta
    # log(1 + e^eta) - y * eta, computed stably
    return weights @ (np.logaddexp(0.0, eta) - y * eta) + 0.5 * pen @ (theta * theta)


def _fit(design: Design, weights: np.ndarray, pen: np.ndarray, theta0: np.ndarray | None = None,
         tol: float = 1e-8, max_iter: int = 50) -> np.ndarray:
    """Weighted ridge logistic regression with soft labels (draws are y = 0.5).

    Newton's method on the sparse, positive definite Hessian. With
    thousands of players who each meet only a few opponents, first-order
    methods converge slowly; Newton needs a handful of steps, and fewer still
    from a warm start.
    """
    X, y = design.X, design.y
    Xt = X.T.tocsr()
    theta = np.zeros(X.shape[1]) if theta0 is None else theta0.copy()
    f = _objective(X, y, weights, pen, theta)
    for _ in range(max_iter):
        eta = X @ theta
        p = 0.5 * (1.0 + np.tanh(0.5 * eta))
        grad = Xt @ (weights * (p - y)) + pen * theta
        hess = (Xt @ sparse.diags(weights * p * (1.0 - p)) @ X + sparse.diags(pen)).tocsr()
        # Conjugate gradients with a diagonal preconditioner: far faster than a
        # direct sparse solve here, where deck columns touch most players.
        step, _ = splinalg.cg(hess, grad, rtol=1e-10, maxiter=1000, M=sparse.diags(1.0 / hess.diagonal()))
        decrement = grad @ step
        if decrement < 2 * tol * max(1.0, abs(f)):
            break
        t = 1.0
        while True:  # backtracking line search; the loss is convex, so this ends quickly
            new = theta - t * step
            f_new = _objective(X, y, weights, pen, new)
            if f_new <= f - 0.25 * t * decrement or t < 1e-4:
                break
            t *= 0.5
        theta, f = new, f_new
    return theta


def _choose_lambda(design: Design, folds: int = CV_FOLDS, grid=LAMBDA_GRID,
                   seed: int = 0) -> tuple[float, dict, np.ndarray | None]:
    """Pick the player penalty by cross-validated log-loss, with whole events held out.

    Also returns, for the chosen penalty, every row's *out-of-fold* ratings
    (an (n, 2) array: player i, player j), fitted without that row's event.
    """
    n_events = design.event.max() + 1
    if n_events < folds:
        return grid[len(grid) // 2], {}, None
    rng = np.random.default_rng(seed)
    fold_of_event = rng.permutation(n_events) % folds
    fold = fold_of_event[design.event]
    scores, oof = {}, {}
    n_p = design.n_players
    for lam in grid:
        total, theta = 0.0, None
        r_oof = np.zeros((len(design.y), 2))
        for k in range(folds):
            train = fold != k
            theta = _fit(design, design.w * train, _penalty(design, lam), theta)
            eta = design.X[~train] @ theta
            ll = np.logaddexp(0.0, eta) - design.y[~train] * eta
            total += design.w[~train] @ ll
            r_oof[~train, 0] = theta[:n_p][design.pi[~train]]
            r_oof[~train, 1] = theta[:n_p][design.pj[~train]]
        scores[lam] = total / design.w.sum()
        oof[lam] = r_oof
    best = min(scores, key=scores.get)
    return best, scores, oof[best]


def _slope_design(design: Design, r_oof: np.ndarray) -> sparse.csr_matrix:
    """Columns: the shared slope b0 (r_i - r_j), then one deviation g_a per archetype
    (+r_i on the player's deck, -r_j on the opponent's; a mirror nets r_i - r_j)."""
    n, n_a = len(design.y), len(design.archetypes)
    ri, rj = r_oof[:, 0], r_oof[:, 1]
    rows = np.concatenate([np.arange(n), np.arange(n), np.arange(n)])
    cols = np.concatenate([np.zeros(n, int), 1 + design.ai, 1 + design.aj])
    vals = np.concatenate([ri - rj, ri, -rj])
    Z = sparse.csr_matrix((vals, (rows, cols)), shape=(n, 1 + n_a))
    Z.sum_duplicates()
    return Z


def _fit_offset(Z: sparse.csr_matrix, y: np.ndarray, w: np.ndarray, offset: np.ndarray, pen: np.ndarray,
                beta0: np.ndarray | None = None, max_iter: int = 30) -> np.ndarray:
    """Small ridge logistic regression with a fixed offset (Newton, dense Hessian)."""
    beta = np.zeros(Z.shape[1]) if beta0 is None else beta0.copy()
    Zt = Z.T.tocsr()
    for _ in range(max_iter):
        eta = offset + Z @ beta
        p = 0.5 * (1.0 + np.tanh(0.5 * eta))
        grad = Zt @ (w * (p - y)) + pen * beta
        hess = (Zt @ sparse.diags(w * p * (1.0 - p)) @ Z).toarray() + np.diag(pen)
        step = np.linalg.solve(hess, grad)
        beta = beta - step
        if np.abs(step).max() < 1e-7:
            break
    return beta


def _skill(design: Design, theta: np.ndarray, r_oof: np.ndarray, bootstrap: int, seed: int) -> pd.DataFrame:
    """Per-archetype skill sensitivity b_a / b0 with a bootstrap 95% interval (resampling events)."""
    Z = _slope_design(design, r_oof)
    offset = design.X[:, design.n_players:] @ theta[design.n_players:]
    pen = np.full(Z.shape[1], SLOPE_LAMBDA)
    pen[0] = 1e-6
    beta = _fit_offset(Z, design.y, design.w, offset, pen)
    n_a = len(design.archetypes)
    counts = np.bincount(design.ai, minlength=n_a) + np.bincount(design.aj, minlength=n_a) \
        - np.bincount(design.ai[design.ai == design.aj], minlength=n_a)
    known = (design.archetypes != UNKNOWN).astype(float) * counts

    def relative(b: np.ndarray) -> np.ndarray:
        slopes = b[0] + b[1:]
        avg = known @ slopes / known.sum()
        return slopes / avg if avg > 0.05 else np.full(n_a, np.nan)

    out = pd.DataFrame({"archetype": design.archetypes, "matches": counts,
                        "slope": beta[0] + beta[1:], "sensitivity": relative(beta)})
    out["ci_low"] = out["ci_high"] = np.nan
    if bootstrap > 0 and known.sum() > 0:
        rng = np.random.default_rng(seed + 1)
        n_events = design.event.max() + 1
        ratios = np.empty((n_a, bootstrap))
        for b in range(bootstrap):
            c = np.bincount(rng.integers(0, n_events, n_events), minlength=n_events)
            ratios[:, b] = relative(_fit_offset(Z, design.y, design.w * c[design.event], offset, pen, beta))
        with np.errstate(all="ignore"):
            out["ci_low"] = np.nanpercentile(ratios, 2.5, axis=1)
            out["ci_high"] = np.nanpercentile(ratios, 97.5, axis=1)
    return out.set_index("archetype")


@dataclass
class PilotFit:
    """Fitted pilot lifts for the matches of one scope, keyed by the matches table index."""
    lift: pd.Series                  # point estimate per match row
    boot: np.ndarray | None = None   # (rows of `lift`, bootstrap replicates)
    lam: float = math.nan
    cv: dict = field(default_factory=dict)
    players: int = 0
    rated: int = 0                   # players with 10+ matches in the window
    skill: pd.DataFrame = field(default_factory=pd.DataFrame)  # per archetype: matches, sensitivity, ci_low/high
    weight_by_source: dict = field(default_factory=dict)  # sum of recency weights of the fitted matches

    @classmethod
    def empty(cls, index: pd.Index) -> "PilotFit":
        return cls(pd.Series(0.0, index=index))

    def sums(self, index: pd.Index, groups: np.ndarray, n_groups: int) -> tuple[np.ndarray, np.ndarray | None]:
        """Sum of lifts per group: the point estimate (n_groups,) and per replicate (n_groups, B).

        `index` are match-table row labels, `groups` their group code (0..n_groups-1).
        Rows the fit doesn't know (shouldn't happen) count as lift 0.
        """
        pos = self.lift.index.get_indexer(index)
        ok = pos >= 0
        point = np.bincount(groups[ok], weights=self.lift.to_numpy()[pos[ok]], minlength=n_groups)
        if self.boot is None:
            return point, None
        ind = sparse.csr_matrix((np.ones(ok.sum()), (groups[ok], pos[ok])), shape=(n_groups, len(self.lift)))
        return point, np.asarray(ind @ self.boot, dtype=float)


def _lifts(design: Design, theta: np.ndarray) -> np.ndarray:
    """Win chance with the players' ratings minus win chance with both ratings at 0."""
    n_p = design.n_players
    skill = design.X[:, :n_p] @ theta[:n_p]
    deck = design.X[:, n_p:] @ theta[n_p:]
    return 1.0 / (1.0 + np.exp(-(skill + deck))) - 1.0 / (1.0 + np.exp(-deck))


def fit(matches: pd.DataFrame, end: pd.Timestamp | str, keep_since: pd.Timestamp | str | None = None,
        lookback_days: int = LOOKBACK_DAYS, half_life_days: float = HALF_LIFE_DAYS,
        bootstrap: int = BOOTSTRAP, seed: int = 0) -> PilotFit:
    """Fit ratings on the `lookback_days` up to `end` and return the pilot lift of every match in that window.

    `matches` should be filtered to one scope (and sources) but not by date.
    Bootstrap lifts are only kept for matches on or after `keep_since`, to
    bound memory. With `bootstrap=0` there is no interval for the lift.
    """
    end = pd.Timestamp(end)
    start = end - timedelta(days=lookback_days - 1)
    window = matches[(matches["date"] >= start) & (matches["date"] <= end)]
    me, opp = _keys(window["player"]), _keys(window["opponent"])
    named = (me != "") & (opp != "")
    window, me, opp = window[named], me[named], opp[named]
    if window.empty or window["event_id"].nunique() < 2:
        return PilotFit.empty(window.index)

    design = _design(window, me, opp, end, half_life_days)
    # Every match is in the table once from each side. Fit on one side only:
    # the model is symmetric, so the other side adds nothing but run time.
    train = _rows(design, (me < opp).to_numpy())
    lam, cv, r_oof = _choose_lambda(train, seed=seed)
    pen = _penalty(train, lam)
    theta = _fit(train, train.w, pen)
    skill = _skill(train, theta, r_oof, bootstrap, seed) if r_oof is not None else pd.DataFrame()

    keep = np.ones(len(window), dtype=bool) if keep_since is None else (window["date"] >= pd.Timestamp(keep_since)).to_numpy()
    kept = _rows(design, keep)
    lift = pd.Series(_lifts(kept, theta), index=window.index[keep])

    boot = None
    if bootstrap > 0:
        rng = np.random.default_rng(seed)
        n_events = design.event.max() + 1
        boot = np.empty((keep.sum(), bootstrap), dtype=np.float32)
        for b in range(bootstrap):
            counts = np.bincount(rng.integers(0, n_events, n_events), minlength=n_events)
            theta_b = _fit(train, train.w * counts[train.event], pen, theta)
            boot[:, b] = _lifts(kept, theta_b)

    matches_per_player = np.bincount(train.X[:, :train.n_players].nonzero()[1], minlength=train.n_players)
    weights = pd.Series(train.w, index=window.index[(me < opp).to_numpy()])
    by_source = weights.groupby(window.loc[weights.index, "source"]).sum()
    return PilotFit(lift, boot, lam, cv, players=train.n_players, rated=int((matches_per_player >= 10).sum()),
                    skill=skill, weight_by_source={str(k): float(v) for k, v in by_source.items()})


def fit_scope(tables: dict[str, pd.DataFrame], scope_sources: set[str] | None, end, keep_since=None,
              sources: list[str] | None = None, bootstrap: int = BOOTSTRAP, seed: int = 0) -> PilotFit:
    """`fit` on the matches of one scope (and optional sources)."""
    m = tables["matches"]
    if scope_sources is not None:
        m = m[m["source"].isin(scope_sources)]
    if sources:
        m = m[m["source"].isin(sources)]
    return fit(m, end, keep_since, bootstrap=bootstrap, seed=seed)
