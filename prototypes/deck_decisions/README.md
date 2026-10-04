# Deck decisions (prototype)

Which cards in a deck are fixed, and which are real deckbuilding decisions? The
prototype the dashboard's "Builds and decisions" section was ported from
(`pauper_research/decisions.py`, view 2 below). Kept for reference.

```bash
python prototypes/deck_decisions/build.py      # needs data/processed/tables.pkl (see the main README)
python -m http.server 8765 --directory prototypes/deck_decisions
```

Then open <http://localhost:8765>. `data.js` is the generated output (aggregates
only, no player names), committed so the page can be viewed without fetching data.

## What it computes (`build.py`)

Per archetype (16 most played, last 90 days, all events) and board:

- **Builds (shells):** a divisive tree of single-card questions ("4+ Moon-Circuit
  Hacker?"), each chosen as the card choice that best predicts the rest of the
  list. Leaves are the builds; each gets a typical list (Frank Karsten's aggregate
  decklist method).
- **Decisions within a build:** fixed cards (85%+ of lists with the same count),
  copy-count decisions ("18 or 19 Mountain"), in/out cards, and slots: groups of
  cards whose combined copies vary much less than each alone, shown as the actual
  splits lists use. Computed inside each build, so another build never shows up
  as a "choice".
- **Win rates:** pilot-adjusted (raw minus average pilot lift, as on the
  dashboard), Wilson / Newcombe intervals moved to the adjusted value; the pilot
  model's own uncertainty is not added (no bootstrap).
- **Matchups per option:** lists with an option against the deck's other lists,
  per opponent with 10+ matches on each side. A permutation test showed these are
  currently no more often "clear" than chance, so treat them as leads.

## Views (`index.html`)

Tabs: Current (first merged design), 1 Annotated list, 2 Ranked decisions (builds
with expandable annotated lists, then decisions with play share, win rate and
matchups; 95% / 90% interval switch), 3 Builds side by side, How it works.

## Open points

- Matchup chips: group opponents (aggro / midrange / control / combo) or use 180
  days to get real signal; hide on the sideboard (confounded by expected field).
- Per-decision verdict line; mirror chips on two-option count decisions.
- Build names can collide ("… build 2").
- Port the chosen view into the dashboard and its Methods page.
