# Pauper-Research

Metagame, matchup and card analysis for Magic: The Gathering **Pauper**, built on
public tournament data.

- **Data:** decklists, round-by-round results and standings from
  [fbettega/MTG_decklistcache](https://github.com/fbettega/MTG_decklistcache)
  (MTGO, Melee, Topdeck.gg, CardsRealm), updated daily.
- **Archetypes:** the community rules in
  [Badaro/MTGOFormatData](https://github.com/Badaro/MTGOFormatData), applied by a
  Python port of [MTGOArchetypeParser](https://github.com/Badaro/MTGOArchetypeParser).
  About 99% of recent decks get a named archetype.

See [SOURCES.md](SOURCES.md) for other data sources and what each is good for.

## Usage

```bash
pip install -e ".[dev]"

python -m pauper_research fetch           # download / update raw data (~900 MB, into data/raw)
python -m pauper_research build           # parse into tables (data/processed/tables.pkl)
python -m pauper_research report --since 2026-07-01            # -> reports/latest/
python -m pauper_research report --since 2026-07-01 --scope paper   # online | paper | combined | all
python -m pauper_research cards "Red Madness" --since 2026-07-01 --scope all   # card-level comparison
```

### Online vs paper

Online and paper data differ a lot (see limitations), so every command takes
`--scope`:

| Scope | Sources | Good for |
|---|---|---|
| `online` | MTGO | Meta share among winning MTGO decks; top-8 matchups only |
| `paper` | Melee, CardsRealm, Topdeck | Matchups and card analysis: every round, lists for nearly every player |
| `combined` (default) | all | Largest sample |
| `all` | each of the above | Writes one subfolder per scope |

Every report also has an **Online vs paper** table that shows each archetype's
share and win rate on both scopes, and flags archetypes where the two clearly
disagree. `--sources` still narrows further, e.g. `--sources MTGmelee`.

### Dashboard

```bash
python -m pauper_research dashboard      # -> reports/dashboard/index.html
```

**Live version:** <https://fmssn.github.io/Pauper-Research/>, rebuilt daily from
the latest data by [`.github/workflows/dashboard.yml`](.github/workflows/dashboard.yml)
(also on every push to `main`, or by hand under Actions → Dashboard → Run workflow).

One self-contained, mobile-first HTML page (open it in a browser, no server
needed). The flow is: pick a deck, see what it's good and bad against, then
see which cards move its win rate, overall and against a specific opponent.

- **Decks:** every top archetype with meta share and win rate. Search and sort.
- **Deck page:** good and bad matchups, most certain first, each with its 95%
  interval and a Clear / Lean label; then the cards whose lists win more or less.
- **Matchup page:** the head-to-head record, plus card comparisons counting
  only matches against that opponent. Shown only when the sample allows it
  (25+ matches in the matchup, 3+ lists and 10+ matches on each side of a card).
- Period (30 / 90 / 180 days), events (all / paper / online) and **pilot skill**
  (adjusted, the default, or raw) in the filter sheet. See
  [Pilot skill](#pilot-skill).
- **Methods:** every formula behind the numbers, rendered from LaTeX, with the
  settings of the current build (link at the bottom of the deck list, or
  `#methods`).
- **Card images:** the eye icon next to a card opens its Scryfall image full
  screen. By default the page links to Scryfall's image server. For hosts that
  block other sites, `--images sheets` (needs `pip install -e ".[images]"`)
  downloads the images once into `data/raw/scryfall/` and writes them next to
  the page as sheets of 9 cards in `cards/`.

`report` writes:

| File | Contents |
|---|---|
| `README.md` | Coverage, meta share and win rate per archetype, matchup matrix of the top archetypes |
| `archetypes.csv` | All archetypes: decks, meta share, non-mirror wins/matches, win rate, 95% CI, pilot lift and pilot-adjusted win rate with its 95% CI, skill sensitivity with its 95% CI |
| `matchups.csv` | Every archetype pair: wins, matches, win rate, 95% CI, pilot lift, pilot-adjusted win rate and CI |
| `matchup_matrix.csv` | Win-rate matrix of the top archetypes |

`cards <archetype>` compares decks of one archetype that play each card against
those that don't (win rate with / without, difference and 95% CI), and lists play
rates and average copies. With the pilot adjustment it also gives each side's
average pilot lift and the difference after removing it (`delta_adj` and its CI).

`report`, `cards` and `dashboard` take `--bootstrap N` (default 100): the number
of refits used for the uncertainty of the pilot adjustment. `--bootstrap 0`
skips them, which is much faster but leaves that uncertainty out of the intervals.

A snapshot for July to September 2026 is in [reports/2026-Q3](reports/2026-Q3/combined/README.md)
(also [online](reports/2026-Q3/online/README.md) and [paper](reports/2026-Q3/paper/README.md)).

## How the numbers are computed

- **Win rate** = non-mirror *match* win rate; draws count as half a win.
  Matches against opponents without a published list count toward the deck's
  overall win rate but not toward any matchup cell.
- **Intervals** are 95% Wilson intervals. Pauper matchup samples are small: even
  with 30 matches, a cell is only accurate to about ±17 points.
- **Meta share** is the share of *published* decklists, so for MTGO it means
  "share among the top 32 and 5-0 lists", not share of the whole field.

## Pilot skill

Raw win rates mix deck strength with pilot strength: a deck that strong players
like to register looks better than it is. `pauper_research/ratings.py` separates
the two.

- **Model.** One regularized Bradley–Terry (logistic) model on match results:
  `logit P(win) = (player − opp_player) + (deck − opp_deck)`. Deck effects are
  per archetype per quarter, so they follow the meta. Opponents without a list
  get an "Unknown" deck. Fitting both together means a player doesn't get credit
  for their deck, and a deck doesn't get credit for its pilots.
- **Data.** The 12 months up to the end of the period, with a 6-month half-life,
  so older results count less. One fit per scope (online / paper / combined).
  Mirror matches are included, since they are the cleanest signal of skill.
- **Players.** Identified by name, normalized (case, whitespace, Unicode) and
  merged across sources; no source has player IDs. Names never appear in any
  report or on the dashboard: only aggregates are published.
- **Shrinkage.** Player ratings get a ridge penalty, chosen per fit by 5-fold
  cross-validation with whole events held out. A player with few matches stays
  close to average.
- **Pilot lift.** For every match, the model's win chance with both players'
  ratings minus the chance with both set to 0. A deck's **pilot-adjusted win
  rate** is its raw win rate minus its average lift over the same matches. The
  same holds for matchup cells, and for the "with" and "without" sides of a card
  comparison.
- **Intervals.** The ratings are refitted on 100 bootstrap resamples of events.
  The lift's spread is added, in quadrature, to the Wilson (or Newcombe) interval.

**Skill sensitivity.** The model above treats a rating edge as worth the same
on every deck. A second fit gives each archetype its own skill slope, using
*out-of-fold* ratings (from the cross-validation fit that held out the match's
event), with a ridge penalty pulling every deck towards the shared slope. A
deck's sensitivity is its slope over the match-weighted average slope: 1 is
average, 1.5 means a rating edge counts 1.5 times as much. Its 95% interval
comes from the same event bootstrap. Each deck page has one plain sentence about
it ("Win rate very sensitive to player skill" only when the whole interval is
above 1), and `archetypes.csv` has `skill_sensitivity` and its CI for decks with
150+ matches in the 12 months. It measures how much skill pays off on a known
deck, not how long the deck takes to learn.

The adjustment is **conservative**. Ratings are shrunk towards average, so for
players with few matches only part of their edge is removed. On simulated data
where strong pilots make an average deck look like a 70% deck, with about 40
matches per player the adjustment brings it back to about 59%, not 50%. It also can't separate skill
from anything else that comes with a player, such as a strong local scene.

## Known limitations

- **MTGO gives few matches.** Since mid-2024 mtgo.com only publishes Challenge
  top-8 brackets and a curated sample of 5-0 League lists. Most match data comes
  from paper events on Melee (mostly Italy) and CardsRealm (mostly Brazil), so
  win rates reflect those scenes more than the MTGO field.
- **Card comparisons are descriptive, not causal.** Decks that play a card differ
  in other ways too (event, date, other cards, and pilot, which the pilot
  adjustment only partly removes). Use them to find leads; see the roadmap.
- Archetype rules are only as current as MTGOFormatData. Check `is_fallback`,
  `is_conflict` and `candidates` in the decks table when a new deck appears.

## Tables

`data/processed/tables.pkl` holds a dict of pandas DataFrames:

| Table | One row per | Key columns |
|---|---|---|
| `events` | tournament | `event_id`, `date`, `source`, `event_type`, `uri` |
| `decks` | decklist | `deck_id`, `event_id`, `player`, `archetype`, `color`, `is_fallback`, `is_conflict` |
| `deck_cards` | deck × card × board | `deck_id`, `card`, `board` (`main`/`side`), `count` |
| `matches` | match, from each player's side | `deck_id`, `opp_deck_id`, `archetype`, `opp_archetype`, `score`, games |

## Roadmap: card performance

The goal is to measure how much an archetype gains or loses from playing,
cutting or swapping specific cards. Planned on top of the current tables:

1. **Adjust for confounders.** A logistic regression on match results
   within an archetype, with card counts as features plus opponent archetype,
   event and time as controls. Player strength is partly covered by the
   [pilot adjustment](#pilot-skill); the ratings from `ratings.py` can serve as
   the player-strength term.
2. **Swap analysis.** Compare lists that differ by a specific swap (card A
   instead of card B), and see how the effect depends on the number of copies.
3. **Per-matchup effects.** Does a sideboard card actually move its target
   matchup?
4. **Join Scryfall data** for card types, mana value and prices.

## Roadmap: dashboard

Planned features:

1. **Meta trends over time.** A weekly series of meta share and win rate per
   archetype. Each deck gets small trend lines and a "Rising" or "Falling" badge
   when its share has clearly changed in the last few weeks.
2. **"What should I play?" calculator.** Expected win rate of every deck against
   a chosen field: the current meta share by default, or a local meta you enter.
   Matchups with few matches are pulled towards 50% according to their sample
   size, and the result shows which matchups drive the edge.
