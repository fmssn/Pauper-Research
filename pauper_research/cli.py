"""Command line entry point: python -m pauper_research <command>."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from . import analysis
from .archetypes import Classifier
from .loader import load
from .sources import DECKLIST_DIR, FORMAT_DIR, fetch_all

ROOT = Path(__file__).resolve().parent.parent
SCOPE_LABELS = {"online": "MTGO", "paper": "Melee, CardsRealm, Topdeck", "combined": "all sources"}
PROCESSED = ROOT / "data" / "processed" / "tables.pkl"
REPORTS = ROOT / "reports"


def build() -> dict[str, pd.DataFrame]:
    classifier = Classifier.from_format_data(FORMAT_DIR)
    tables = load(DECKLIST_DIR, classifier)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(tables, PROCESSED)
    print(f"Built {len(tables['events'])} events, {len(tables['decks'])} decks, "
          f"{len(tables['matches']) // 2} matches -> {PROCESSED.relative_to(ROOT)}")
    return tables


def _tables() -> dict[str, pd.DataFrame]:
    if not PROCESSED.exists():
        return build()
    return pd.read_pickle(PROCESSED)


def _pct(x: float) -> str:
    return "" if pd.isna(x) else f"{x:.0%}"


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def _scope_section(period_tables: dict[str, pd.DataFrame], archetypes: list[str]) -> str:
    comp = analysis.scope_comparison(period_tables, archetypes)

    def wr(row, scope: str) -> str:
        n = row[f"{scope}_matches"]
        return "" if n == 0 else f"{_pct(row[f'{scope}_win_rate'])} ({n})"

    rows = [[r["archetype"], _pct(r["online_share"]), _pct(r["paper_share"]),
             wr(r, "online"), wr(r, "paper"), wr(r, "combined"), "**yes**" if r["skew"] else ""]
            for _, r in comp.iterrows()]
    table = pd.DataFrame(rows, columns=["Archetype", "Online share", "Paper share", "Online WR (n)",
                                        "Paper WR (n)", "Combined WR (n)", "Skew"])
    return f"""## Online vs paper

The same archetypes measured on each scope. Online win rates come almost
entirely from MTGO top-8 brackets, so they compare strong decks against each
other and have small samples. **Skew = yes** means the online and paper 95%
intervals don't overlap: the two scenes clearly disagree about that deck.

{_md_table(table)}
"""


def report(since: str, until: str | None, sources: list[str] | None, top: int, min_matches: int,
           out_dir: Path, scope: str = "combined") -> Path:
    period_tables = analysis.filter_period(_tables(), since, until, sources)
    tables = analysis.filter_period(period_tables, scope=scope)
    decks, matches, events = tables["decks"], tables["matches"], tables["events"]
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = analysis.archetype_summary(decks, matches)
    matchups = analysis.matchup_table(matches)
    summary.to_csv(out_dir / "archetypes.csv", index=False)
    matchups.to_csv(out_dir / "matchups.csv", index=False)

    top_archs = [a for a in summary["archetype"] if a != "Unknown"][:top]
    rates = analysis.matchup_matrix(matchups, top_archs, "win_rate")
    counts = analysis.matchup_matrix(matchups, top_archs, "matches")
    rates.to_csv(out_dir / "matchup_matrix.csv")

    def cell(a: str, b: str) -> str:
        if a == b:
            return "—"
        n = counts.loc[a, b]
        if pd.isna(n) or n < min_matches:
            return "·"
        return f"{rates.loc[a, b]:.0%} ({int(n)})"

    matrix_md = pd.DataFrame(
        [[a] + [cell(a, b) for b in top_archs] for a in top_archs],
        columns=["Deck \\ vs"] + [str(i + 1) for i in range(len(top_archs))],
    )
    legend = ", ".join(f"{i + 1} = {a}" for i, a in enumerate(top_archs))

    arch_md = summary.head(top).assign(
        share=lambda d: d["share"].map(_pct),
        win_rate=lambda d: d["win_rate"].map(_pct),
        ci=lambda d: [f"{_pct(lo)}–{_pct(hi)}" if not pd.isna(lo) else "" for lo, hi in zip(d["ci_low"], d["ci_high"])],
    )[["archetype", "decks", "share", "matches", "win_rate", "ci"]]
    arch_md.columns = ["Archetype", "Decks", "Meta share", "Non-mirror matches", "Win rate", "95% CI"]

    coverage = events.groupby(["source", "event_type"]).size().rename("events").reset_index()
    match_src = (matches.groupby("source").size() // 2).rename("matches")
    coverage = coverage.merge(match_src, left_on="source", right_index=True, how="left").fillna({"matches": 0})
    coverage["matches"] = coverage["matches"].astype(int).astype(object)
    # Matches are attributed to the source, not the event type, so show them once per source.
    coverage.loc[coverage.duplicated("source"), "matches"] = ""

    period = f"{since} to {until or decks['date'].max().date()}"
    text = f"""# Pauper metagame report

Period: **{period}** · scope: **{scope}** ({SCOPE_LABELS[scope]}){f" · sources: {', '.join(sources)}" if sources else ""}
· {len(events)} events · {len(decks)} decklists · {len(matches) // 2} matches with results

## Data coverage

{_md_table(coverage)}

MTGO only publishes top-8 brackets for Challenges and a sample of 5-0 League
lists, so MTGO contributes many decklists but few matches. Most matchup data
comes from paper events on Melee and CardsRealm, which skew towards Italian and
Brazilian local events.

## Archetypes

Meta share is the share of published decklists. Win rate is non-mirror match
win rate (draws count as half). The interval is a 95% Wilson interval: if two
decks' intervals overlap heavily, the data can't tell them apart.

{_md_table(arch_md)}

## Matchups (top {len(top_archs)} archetypes)

Row deck's match win rate against the column deck, with the number of matches.
`·` = fewer than {min_matches} matches. {legend}.

{_md_table(matrix_md)}

Even at 30 matches, a matchup's 95% interval is about ±17 points wide. Full
long-form data with intervals: `matchups.csv`.

{_scope_section(period_tables, top_archs)}"""
    path = out_dir / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


def cards(archetype: str, since: str, until: str | None, sources: list[str] | None, board: str,
          min_decks: int, out_dir: Path, scope: str = "combined") -> None:
    tables = analysis.filter_period(_tables(), since, until, sources, scope)
    decks = tables["decks"]
    if archetype not in set(decks["archetype"]):
        close = [a for a in decks["archetype"].unique() if archetype.lower() in a.lower()]
        raise SystemExit(f"No decks for archetype {archetype!r}. Did you mean: {', '.join(close) or 'n/a'}?")
    impact = analysis.card_impact(decks, tables["deck_cards"], tables["matches"], archetype, board, min_decks)
    plays = analysis.card_play_rates(decks, tables["deck_cards"], archetype)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = archetype.lower().replace(" ", "-")
    impact.to_csv(out_dir / f"cards-{slug}-impact.csv", index=False)
    plays.to_csv(out_dir / f"cards-{slug}-play-rates.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 60):
        cols = ["card", "decks_with", "decks_without", "matches_with", "matches_without",
                "win_rate_with", "win_rate_without", "delta", "delta_ci_low", "delta_ci_high"]
        print(impact[cols].round(3).to_string(index=False) if not impact.empty else "Not enough data.")
    print(f"\nWrote {out_dir / f'cards-{slug}-impact.csv'} and play rates.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pauper_research")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download or update the raw data")
    sub.add_parser("build", help="parse raw data into tables")

    default_since = (date.today() - timedelta(days=90)).isoformat()
    for name in ("report", "cards"):
        p = sub.add_parser(name)
        p.add_argument("--since", default=default_since, help="start date, YYYY-MM-DD (default: 90 days ago)")
        p.add_argument("--until", default=None)
        p.add_argument("--sources", nargs="*", help="e.g. MTGO MTGmelee CardsRealm Topdeck")
        p.add_argument("--scope", choices=[*analysis.SCOPES, "all"], default="combined",
                       help="online (MTGO), paper (Melee, CardsRealm, Topdeck), combined, or all three")
        p.add_argument("--out", type=Path, default=REPORTS / "latest")
    sub.choices["report"].add_argument("--top", type=int, default=15)
    sub.choices["report"].add_argument("--min-matches", type=int, default=8)
    sub.choices["cards"].add_argument("archetype")
    sub.choices["cards"].add_argument("--board", choices=["main", "side"], default="main")
    sub.choices["cards"].add_argument("--min-decks", type=int, default=5)

    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch_all()
        return
    if args.command == "build":
        build()
        return
    scopes = list(analysis.SCOPES) if args.scope == "all" else [args.scope]
    for scope in scopes:
        # With several scopes, each gets its own subfolder.
        out = args.out / scope if len(scopes) > 1 else args.out
        if args.command == "report":
            path = report(args.since, args.until, args.sources, args.top, args.min_matches, out, scope)
            print(f"Wrote {path}")
        elif args.command == "cards":
            print(f"\n== {args.archetype} · {scope} ==")
            cards(args.archetype, args.since, args.until, args.sources, args.board, args.min_decks, out, scope)
