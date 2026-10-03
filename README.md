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
- Period (30 / 90 / 180 days) and events (all / paper / online) in the filter sheet.
- **Card images:** the eye icon next to a card opens its Scryfall image full
  screen. By default the page links to Scryfall's image server. For hosts that
  block other sites, `--images sheets` (needs `pip install -e ".[images]"`)
  downloads the images once into `data/raw/scryfall/` and writes them next to
  the page as sheets of 9 cards in `cards/`.

`report` writes:

| File | Contents |
|---|---|
| `README.md` | Coverage, meta share and win rate per archetype, matchup matrix of the top archetypes |
| `archetypes.csv` | All archetypes: decks, meta share, non-mirror wins/matches, win rate, 95% CI |
| `matchups.csv` | Every archetype pair: wins, matches, win rate, 95% CI |
| `matchup_matrix.csv` | Win-rate matrix of the top archetypes |

`cards <archetype>` compares decks of one archetype that play each card against
those that don't (win rate with / without, difference and 95% CI), and lists play
rates and average copies.

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

## Known limitations

- **MTGO gives few matches.** Since mid-2024 mtgo.com only publishes Challenge
  top-8 brackets and a curated sample of 5-0 League lists. Most match data comes
  from paper events on Melee (mostly Italy) and CardsRealm (mostly Brazil), so
  win rates reflect those scenes more than the MTGO field.
- **Card comparisons are descriptive, not causal.** Decks that play a card differ
  in other ways too (pilot, event, date, other cards). Use them to find leads;
  see the roadmap.
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
   event and time as controls, ideally with a player-strength term.
2. **Swap analysis.** Compare lists that differ by a specific swap (card A
   instead of card B), and see how the effect depends on the number of copies.
3. **Per-matchup effects.** Does a sideboard card actually move its target
   matchup?
4. **Join Scryfall data** for card types, mana value and prices.
