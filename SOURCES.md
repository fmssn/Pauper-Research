# Data sources for Pauper analysis

Checked October 2026.

## Raw data (used by this repo)

| Source | What it has | Notes |
|---|---|---|
| [fbettega/MTG_decklistcache](https://github.com/fbettega/MTG_decklistcache) | JSON per tournament from MTGO, Melee, Topdeck.gg, CardsRealm and Manatraders: decklists, round pairings and results, standings | **Primary source.** Updates daily. Successor to the Badaro cache. |
| [Badaro/MTGOFormatData](https://github.com/Badaro/MTGOFormatData) | Archetype definitions and card colors for each format | Used for archetype detection. |
| [Badaro/MTGODecklistCache](https://github.com/Badaro/MTGODecklistCache) / [Jiliac fork](https://github.com/Jiliac/MTGODecklistCache) | Same format, older data | Archived June 2025. Use for history before then. |
| mtgo.com/decklists | Official Challenge and League lists | Limited since mid-2024: top-8 brackets and a curated 5-0 sample only. |
| Scryfall API / bulk data, MTGJSON | Card data, Pauper legality, prices and price history | For joining card attributes. Not yet used. |

## Other scrapers and tools

- [modometa-scraper](https://github.com/davidfischer/modometa-scraper): MTGO challenge and league scraper.
- [mtgodecklists](https://github.com/YrielPenguin/mtgodecklists): gathers and classifies MTGO lists.
- [mtg-meta-analyzer](https://github.com/Zuxas/mtg-meta-analyzer): scrapes MTGTop8, MTGDecks and Melee; builds matchup matrices.

## Dashboards (for checking our numbers)

- [magicmeta.net Pauper matchups](https://magicmeta.net/formats/pauper/matchups): MTGO playoffs, Topdeck and Gatherling leagues.
- [Pauper Analytics Dashboard](https://fnpavel.github.io/pauperdata/): Kirblinxy's historical MTGO dataset (no longer updated), with CSV export.
- [MTGGoldfish Pauper](https://www.mtggoldfish.com/metagame/pauper) and the monthly "Power of Pauper" articles.
- [MTGDecks.net Pauper](https://mtgdecks.net/Pauper), [Cardsrealm win rates](https://mtg.cardsrealm.com/en-us/meta-decks/pauper/win-rate-per-deck), [Magic4ever tracker](https://www.magic4ever.com/pauper/).
- [MyMTGO](https://mymtgo.com/): tracks your own MTGO matches from the logs.
