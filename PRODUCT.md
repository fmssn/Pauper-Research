# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Competitive Pauper grinders, on paper and MTGO, getting ready for a Challenge, RCQ or
local event. They come to answer concrete questions: which deck to register, how it
does against the decks they expect to face, and which cards, copy counts and builds
actually move its win rate. They often look things up on a phone at the venue or
between rounds, not only at a desk.

## Product Purpose

Pauper-Research turns public tournament data (decklists, round-by-round results and
standings from MTGO, Melee, Topdeck.gg and CardsRealm) into metagame, matchup and card
statistics. The main surface is a dashboard rebuilt daily and published at
<https://fmssn.github.io/Pauper-Research/>. The flow is: pick a deck, see what it is
good and bad against, then see which cards and build decisions change its win rate,
both overall and against a specific opponent. CLI reports (`report`, `cards`) produce
the same numbers as Markdown and CSV.

The product succeeds when a grinder leaves with a decision they can defend: a deck,
a 75, a sideboard plan, and an honest sense of how sure the numbers are.

## Positioning

**Proper statistics, not raw decklists.** Meta sites list decks and share. This one
gives win rates with 95% intervals, Clear or Lean verdicts, and an optional correction
for pilot skill. It goes beyond meta share to card, copy-count, slot and build
decisions within a deck. Every method is documented with its formula on the Methods
page and can be reproduced from public data.

## Operating Context

- Used to prepare for events and during them: choosing a deck, tuning the main deck
  and sideboard, checking a matchup before a round.
- Filters: period (30 / 90 / 180 days), events (all / paper / online), and pilot-skill
  correction (on or off).
- Data reality: since mid-2024 MTGO publishes only Challenge top 8s and a curated set
  of 5-0 League lists. Most match data comes from paper events (Melee, mostly Italy;
  CardsRealm, mostly Brazil). Share of lists and win rates often come from different
  sources, and the dashboard says which.
- Archetype names come from the community rules in Badaro/MTGOFormatData.

## Capabilities and Constraints

- **Phones are first-class.** Every view must work fully on a phone, not as a reduced
  version of the desktop page. (Confirmed.)
- **Methods page stays in sync.** Any new or changed statistic, interval, model,
  weighting or display threshold updates the Methods page in the same change, with
  settings exposed from code, never hard-coded in text (see CLAUDE.md).
- Current implementation, not re-confirmed as a binding constraint: one self-contained
  HTML page built by Python (`pauper_research/dashboard_template.html`), deployed to
  GitHub Pages by a daily workflow. It has light and dark themes, aims for WCAG AA
  contrast, and supports keyboard and screen readers.
- Player names are never published. Only aggregates appear in reports and on the
  dashboard (current README policy).
- Card comparisons are descriptive, not causal. Matchup samples are small, so much of
  the data is "Lean" rather than "Clear", and the product has to show that honestly.
- Terminology in use: meta share, win rate (non-mirror match win rate, draws count
  half), Clear / Lean, pilot lift, pilot-adjusted win rate, skill sensitivity,
  builds, slots, copy-count decisions, in/out cards, fixed cards.
- Planned (README roadmap): meta trends over time with Rising / Falling badges, and a
  "What should I play?" field calculator.

## Evidence on Hand

- Live data, rebuilt daily from fbettega/MTG_decklistcache.
- Snapshot report for July–September 2026: `reports/2026-Q3/` (combined, online, paper).
- Methods documentation: README "How the numbers are computed" and "Pilot skill", and
  the dashboard Methods page.
- No testimonials, user counts, press or endorsements. Do not invent them.

## Product Principles

1. **Certainty before magnitude.** A number without its uncertainty is not shown as a
   finding. Clear results lead; Lean results are labelled and kept apart.
2. **Answer the grinder's next decision.** Deck, then matchups, then cards and builds.
   Every view should lead to the next choice the player has to make.
3. **Show the work.** Every figure can be traced to a documented formula and its
   current settings.
4. **Works at the venue.** A phone between rounds is a primary setting, not an
   afterthought.
5. **Say where the data comes from.** Online and paper data differ, so the source mix
   behind each number is always visible.
