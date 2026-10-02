# Pauper metagame report

Period: **2026-07-01 to 2026-09-30** · scope: **online** (MTGO)
· 186 events · 5203 decklists · 602 matches with results

## Data coverage

| source | event_type | events | matches |
|---|---|---|---|
| MTGO | challenge | 84 | 602 |
| MTGO | league | 94 |  |
| MTGO | other | 6 |  |
| MTGO | qualifier | 2 |  |

MTGO only publishes top-8 brackets for Challenges and a sample of 5-0 League
lists, so MTGO contributes many decklists but few matches. Most matchup data
comes from paper events on Melee and CardsRealm, which skew towards Italian and
Brazilian local events.

## Archetypes

Meta share is the share of published decklists. Win rate is non-mirror match
win rate (draws count as half). The interval is a 95% Wilson interval: if two
decks' intervals overlap heavily, the data can't tell them apart.

| Archetype | Decks | Meta share | Non-mirror matches | Win rate | 95% CI |
|---|---|---|---|---|---|
| Red Madness | 651 | 13% | 170 | 50% | 43%–57% |
| Mono Blue Terror | 496 | 10% | 113 | 48% | 39%–57% |
| Tron | 274 | 5% | 66 | 39% | 29%–51% |
| Jund Midrange | 272 | 5% | 67 | 48% | 36%–60% |
| Red Rally | 267 | 5% | 41 | 51% | 36%–66% |
| Elves | 253 | 5% | 60 | 47% | 35%–59% |
| Grixis Affinity | 227 | 4% | 73 | 45% | 34%–57% |
| Gruul Ponza | 213 | 4% | 58 | 50% | 38%–62% |
| Jeskai Ephemerate | 206 | 4% | 45 | 53% | 39%–67% |
| Spy Combo | 202 | 4% | 19 | 37% | 19%–59% |
| Dimir Faeries | 190 | 4% | 40 | 48% | 33%–63% |
| Mono Blue Faeries | 188 | 4% | 54 | 57% | 44%–70% |
| White Aggro | 181 | 3% | 43 | 58% | 43%–72% |
| Gates | 154 | 3% | 38 | 58% | 42%–72% |
| Dimir Terror | 133 | 3% | 26 | 58% | 39%–74% |

## Matchups (top 15 archetypes)

Row deck's match win rate against the column deck, with the number of matches.
`·` = fewer than 8 matches. 1 = Red Madness, 2 = Mono Blue Terror, 3 = Tron, 4 = Jund Midrange, 5 = Red Rally, 6 = Elves, 7 = Grixis Affinity, 8 = Gruul Ponza, 9 = Jeskai Ephemerate, 10 = Spy Combo, 11 = Dimir Faeries, 12 = Mono Blue Faeries, 13 = White Aggro, 14 = Gates, 15 = Dimir Terror.

| Deck \ vs | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Red Madness | — | 29% (17) | 60% (10) | 79% (14) | · | 91% (11) | 58% (12) | 67% (12) | 40% (10) | · | · | 41% (22) | · | · | · |
| Mono Blue Terror | 71% (17) | — | 82% (11) | 50% (12) | · | · | 57% (14) | · | 30% (10) | · | · | · | · | · | · |
| Tron | 40% (10) | 18% (11) | — | · | · | · | · | · | · | · | · | · | · | · | · |
| Jund Midrange | 21% (14) | 50% (12) | · | — | · | · | · | · | · | · | · | · | · | · | · |
| Red Rally | · | · | · | · | — | · | · | · | · | · | · | · | · | · | · |
| Elves | 9% (11) | · | · | · | · | — | · | · | · | · | · | · | · | · | · |
| Grixis Affinity | 42% (12) | 43% (14) | · | · | · | · | — | · | · | · | · | · | · | · | · |
| Gruul Ponza | 33% (12) | · | · | · | · | · | · | — | · | · | · | · | · | · | · |
| Jeskai Ephemerate | 60% (10) | 70% (10) | · | · | · | · | · | · | — | · | · | · | · | · | · |
| Spy Combo | · | · | · | · | · | · | · | · | · | — | · | · | · | · | · |
| Dimir Faeries | · | · | · | · | · | · | · | · | · | · | — | · | · | · | · |
| Mono Blue Faeries | 59% (22) | · | · | · | · | · | · | · | · | · | · | — | · | · | · |
| White Aggro | · | · | · | · | · | · | · | · | · | · | · | · | — | · | · |
| Gates | · | · | · | · | · | · | · | · | · | · | · | · | · | — | · |
| Dimir Terror | · | · | · | · | · | · | · | · | · | · | · | · | · | · | — |

Even at 30 matches, a matchup's 95% interval is about ±17 points wide. Full
long-form data with intervals: `matchups.csv`.

## Online vs paper

The same archetypes measured on each scope. Online win rates come almost
entirely from MTGO top-8 brackets, so they compare strong decks against each
other and have small samples. **Skew = yes** means the online and paper 95%
intervals don't overlap: the two scenes clearly disagree about that deck.

| Archetype | Online share | Paper share | Online WR (n) | Paper WR (n) | Combined WR (n) | Skew |
|---|---|---|---|---|---|---|
| Red Madness | 13% | 8% | 50% (170) | 48% (1651) | 48% (1821) |  |
| Mono Blue Terror | 10% | 5% | 48% (113) | 50% (965) | 50% (1078) |  |
| Tron | 5% | 4% | 39% (66) | 50% (851) | 49% (917) |  |
| Jund Midrange | 5% | 4% | 48% (67) | 48% (950) | 48% (1017) |  |
| Red Rally | 5% | 5% | 51% (41) | 52% (938) | 52% (979) |  |
| Elves | 5% | 4% | 47% (60) | 53% (814) | 53% (874) |  |
| Grixis Affinity | 4% | 8% | 45% (73) | 51% (1673) | 51% (1746) |  |
| Gruul Ponza | 4% | 2% | 50% (58) | 55% (351) | 55% (409) |  |
| Jeskai Ephemerate | 4% | 3% | 53% (45) | 51% (525) | 51% (570) |  |
| Spy Combo | 4% | 3% | 37% (19) | 59% (687) | 58% (706) |  |
| Dimir Faeries | 4% | 3% | 48% (40) | 52% (720) | 52% (760) |  |
| Mono Blue Faeries | 4% | 3% | 57% (54) | 52% (525) | 53% (579) |  |
| White Aggro | 3% | 4% | 58% (43) | 49% (724) | 49% (767) |  |
| Gates | 3% | 4% | 58% (38) | 55% (942) | 55% (980) |  |
| Dimir Terror | 3% | 3% | 58% (26) | 48% (554) | 49% (580) |  |
