---
name: Pauper-Research
description: Metagame, matchup and card statistics for MTG Pauper, with honest uncertainty.
colors:
  paper: "#ffffff"
  sunken: "#f4f5f6"
  hover: "#eef0f2"
  ink: "#1b2230"
  ink-secondary: "#464e5c"
  muted: "#5f6776"
  hairline: "#e5e8ed"
  hairline-strong: "#cdd2da"
  ui-line: "#7d8490"
  favoured-blue: "#2a78d6"
  favoured-blue-ink: "#1f66bd"
  unfavoured-red: "#e34948"
  unfavoured-red-ink: "#c42f2e"
  neutral: "#878d96"
  focus: "#1f66bd"
  dark-paper: "#11161e"
  dark-sunken: "#19202a"
  dark-hover: "#202833"
  dark-ink: "#eef1f5"
  dark-ink-secondary: "#c1c8d2"
  dark-muted: "#8b94a3"
  dark-hairline: "#262e3a"
  dark-hairline-strong: "#37414f"
  dark-ui-line: "#68727f"
  dark-favoured-blue: "#3987e5"
  dark-favoured-blue-ink: "#5c9df0"
  dark-unfavoured-red: "#e66767"
  dark-unfavoured-red-ink: "#ef7676"
  dark-neutral: "#7a818b"
  dark-focus: "#5598e7"
  mana-W: "#f4eed2"
  mana-U: "#a9cdea"
  mana-B: "#b7aca3"
  mana-R: "#ec9f80"
  mana-G: "#9cc598"
  mana-C: "#d3d5d9"
  mana-ink: "#1c1c1a"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "36px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "-0.005em"
  stat:
    fontFamily: "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.15
    fontFeature: "tnum"
  body:
    fontFamily: "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "IBM Plex Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.45
  code:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  bar: "2px"
  sm: "4px"
  md: "6px"
  lg: "12px"
spacing:
  xxs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    height: "46px"
    typography: "{typography.body}"
  segmented-option:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "34px"
  segmented-option-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  segmented-option-hover:
    backgroundColor: "{colors.hover}"
  chip-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "34px"
  icon-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    size: "40px"
  input-search:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 12px 0 36px"
    height: "44px"
  deck-row:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "8px 8px 8px 4px"
    height: "56px"
  deck-row-current:
    backgroundColor: "{colors.sunken}"
  chip:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "4px 9px"
  matchup-chip:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.sm}"
    padding: "1px 7px"
  tag-clear-good:
    textColor: "{colors.favoured-blue-ink}"
    typography: "{typography.label}"
  tag-clear-bad:
    textColor: "{colors.unfavoured-red-ink}"
    typography: "{typography.label}"
  tag-lean:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  panel:
    backgroundColor: "{colors.sunken}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  filter-sheet:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "20px 16px"
---

# Design System: Pauper-Research

## Overview

**Creative North Star: "The Lab Notebook"**

The dashboard reads like a careful researcher's notebook: plain sans-serif entries in
tabular figures, a single serif voice for the thing being studied (a deck's name, a
matchup), and every claim annotated with how sure it is. Nothing on the page is
decorative. Structure comes from hairline rules and whitespace, not from boxes,
shadows or colour fields. The method is always one link away, because in a notebook
you show your working.

Density is high but calm. A grinder scrolls long lists of decks, matchups and cards,
so rows are tight, numbers line up, and hierarchy comes from weight and size steps
inside one sans family rather than from colour. Colour is reserved for a single
meaning: whether a result favours the deck (blue) or not (red). Grey carries
everything else. Certainty is drawn, not written: a solid bar is a Clear result, an
outlined bar is a Lean one, and every bar carries the whisker of its 95% interval.

The system is mobile-first and theme-symmetric. Phones get one stacked column with
44px touch targets; from 1024px a sidebar of decks sits beside the detail; from
1600px matchups and cards stand side by side. Light and dark themes share every
role, and both meet WCAG AA.

**Key Characteristics:**
- Rules, not boxes: sections are separated by 1px hairlines, never by cards with shadows.
- One meaning colour pair (Favoured Blue / Unfavoured Red); everything else is ink on paper.
- Serif only for the subject (deck or matchup names, page titles); sans for all data.
- Tabular numerals everywhere numbers sit in columns.
- Certainty is encoded in the mark: solid fill = Clear, outline = Lean, whisker = 95% interval.
- Quiet, precise controls: hairline borders, 6px radius, ink-filled when selected.

## Colors

A cool ink-on-paper neutral scale carrying one diverging pair whose only job is to say
"favoured" or "unfavoured".

### Primary
- **Favoured Blue** (`favoured-blue`): fills for bars, chart dots and Clear results that
  favour the deck: above 50% win rate, or a card whose lists win more. Its darker text
  version, **Favoured Blue Ink** (`favoured-blue-ink`), is used whenever the colour
  carries text (Clear tags, "Good against" headings, links in Methods), because it
  reaches 4.5:1 on every surface.
- **Unfavoured Red** (`unfavoured-red`): the mirror of Favoured Blue for results below
  50% or cards whose lists win less. **Unfavoured Red Ink** (`unfavoured-red-ink`) for
  text.

### Neutral
- **Paper** (`paper`): the page and every control's resting background.
- **Sunken** (`sunken`): recessed surfaces: the build panel, empty states, chips,
  the Methods summary box, the current deck row.
- **Hover** (`hover`): the hover and expanded state of rows, chips and icon buttons.
- **Ink** (`ink`): primary text, and the fill of selected segmented options and the
  primary button (with Paper text).
- **Ink Secondary** (`ink-secondary`): body copy in notes, verdicts and Methods prose;
  unselected control labels.
- **Muted** (`muted`): metadata: ranks, subtitles, counts, axis labels, Lean tags.
- **Hairline** (`hairline`) and **Hairline Strong** (`hairline-strong`): row dividers
  and control borders, respectively.
- **UI Line** (`ui-line`): the bars' 50% centre line and input borders, at 3:1 against
  every surface.
- **Neutral** (`neutral`): metagame chart dots whose 95% interval crosses 50%
  (legend: "Could be even"); clearly above or below 50% they take blue or red.
- **Focus** (`focus`): the 2px focus ring, offset 2px.

The dark theme (`dark-*` tokens) swaps each role one for one, lifting the blue and red
so they keep the same contrast against the near-black paper. It applies under
`prefers-color-scheme: dark` unless `data-theme="light"` is set, and always under
`data-theme="dark"`.

### Mana
`mana-W`, `mana-U`, `mana-B`, `mana-R`, `mana-G` and `mana-C` fill the small round
colour-identity pips beside deck names, always with `mana-ink` letters. They are
pastel on purpose so they never compete with Favoured Blue or Unfavoured Red.

### Named Rules
**The One Meaning Rule.** In data, blue and red mean "favoured" and "unfavoured",
nothing else: no red warnings, no branded accents. If a mark does not answer "does this
help the deck?", it is grey. The only other uses of blue are interaction cues, kept
deliberately thin: link buttons and Methods links (Favoured Blue Ink, underlined) and
the focus ring.

**The Ink Twin Rule.** Every meaning colour has a fill version for marks and an ink
version for text. Text never uses the fill version.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif)
**Body Font:** IBM Plex Sans (with system-ui, -apple-system, Segoe UI, sans-serif)
**Label/Mono Font:** ui-monospace, SFMono-Regular, Menlo (code in Methods only)

**Character:** A bookish serif names the subject; a technical, even-handed sans with
tabular figures records the measurements. Only weights 400, 500 and 600 are loaded.

### Hierarchy
- **Display** (`display`; 30px on phones): the deck or matchup name in the page
  header, and the metagame chart title.
- **Headline** (`headline`; 22px in the desktop sidebar): the deck-list intro title.
- **Title** (`title`): section headings ("Matchups", "Cards"). Subsection headings drop
  to 14–16px at the same weight.
- **Stat** (`stat`): the three headline numbers in the deck header (meta share, win
  rate, matches).
- **Body** (`body`; 15px from 1024px): running text. Notes and verdicts sit at 14–15px
  in Ink Secondary with a 72ch measure; Methods prose at 62ch.
- **Label** (`label`): filter labels, column heads, tags, metadata. Row metadata goes
  down to 12–13px in Muted.
- **Code** (`code`): inline code and formula variable names on the Methods page.

### Named Rules
**The Serif Names the Subject Rule.** Source Serif 4 is used only for what the page
is about: a deck, a matchup, the page title. Never for numbers, labels or controls.

**The Tabular Rule.** Any number that can sit above or below another number uses
`font-variant-numeric: tabular-nums`.

## Layout

Mobile-first, one column of stacked views (deck list → deck → matchup → Methods),
16px side padding, 20–24px vertical gaps between sections.

- **Below 1024px:** a sticky 56px top bar holds a back button, the current deck and a
  Filters button that opens a bottom sheet. All touch targets are at least 44px tall;
  card chips are 40px because they form a dense cloud. Below 520px chip buttons switch
  to short labels.
- **From 1024px:** a two-column app. The deck list becomes a sticky, independently
  scrolling sidebar (320px, 380px from 1200px, 420px from 1600px) separated by a
  hairline. The filters move into the top bar as compact segmented controls, and
  breadcrumbs follow the brand. Matchup and card rows go onto one line: name | bar |
  value.
- **1024–1279px:** filter labels and the Methods link text are dropped to make room
  for breadcrumbs.
- **From 1600px:** the deck view splits into matchups and cards side by side (48px
  gap), with builds and decisions spanning both below.
- **Methods:** a single centred 760px reading column with a sticky table of contents.

Spacing follows a 4px base with common steps of 8, 12/14, 16, 24 and 32px. Rows are
tight (8–10px vertical padding); sections breathe (24px gaps).

## Elevation & Depth

Flat. Depth is conveyed by tone (Sunken surfaces recessed below Paper) and by
hairlines, not by shadows. The only shadows in the system belong to things that
genuinely float above the page: the chart tooltip and the full-screen card image.
Modal layers dim the page with a translucent backdrop instead.

### Shadow Vocabulary
- **Tooltip** (`box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12)`): the metagame chart's
  hover tooltip.
- **Card image** (`box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6)`): the Scryfall card
  image in the viewer.
- **Current-row marker** (`box-shadow: inset 2px 0 0 var(--ink)`): not elevation; a
  2px ink edge marking the selected deck row and decision lines in a decklist.

### Named Rules
**The Rules-Not-Boxes Rule.** Sections are separated by a 1px hairline and space. Do
not wrap content in bordered or shadowed cards.

## Shapes

Small, consistent radii. Controls, panels and inputs use 6px; chips and inline code
4px; bar fills 2px; the filter sheet 12px (top corners only on phones). Mana pips and
chart dots are full circles. Borders are 1px hairlines; the only thicker lines are the
2px focus ring and the 2px selection edge.

## Components

### Buttons
- **Shape:** gently rounded (6px).
- **Primary** (`button-primary`): Ink fill with Paper text, 46px tall, weight 600.
  Used once, to apply filters in the sheet.
- **Icon button** (`icon-button`): 40px transparent square with a 20px stroke icon
  (2px stroke, round caps); Hover fill on hover.
- **Chip button** (`chip-button`): 34px (44px on touch) with a Hairline Strong
  border, used for the Filters trigger.
- **Link button:** Favoured Blue Ink text, underlined with a 3px offset; for
  in-flow actions like "Show all" or "Copy list".

### Segmented Control
- **Style:** one Hairline Strong outline around 2–3 options, 1px dividers between
  them, 6px outer radius.
- **State:** the pressed option is Ink-filled with Paper text (`segmented-option-pressed`);
  others are Ink Secondary on Paper, Hover on hover. 30px in the desktop top bar, 44px
  on touch.

### Chips
- **Card chip** (`chip`): Sunken fill, 4px radius, 13px text with a tabular count in
  weight 600.
- **Matchup chip** (`matchup-chip`): a tighter 12px chip for an option's matchups.
  Clear results get a 1px inset outline in Favoured Blue Ink or Unfavoured Red Ink.

### Inputs / Fields
- **Search** (`input-search`): 44px (36px on desktop), UI Line border, 6px radius,
  18px magnifier icon inset left in Muted.
- **Focus:** the global 2px Focus ring at a 2px offset.

### Navigation
- **Top bar:** sticky, Paper with a Hairline bottom border, 56px. The brand (title and
  date range) always links home on desktop, followed by breadcrumbs in Ink Secondary
  with the current page in Ink weight 600. On phones, a back button and the current
  context replace both.
- **Deck row** (`deck-row`): rank | name with mana pips and metadata | win rate with a
  72px mini bar. Hover fill on hover; the current deck gets a Sunken fill and a 2px Ink
  left edge.

### Diverging Bar (signature component)
The core mark of the system. An 18px-tall strip with a 2px Hairline track, a 1px UI
Line centre line at 50% (or 0 points), an 8px fill from the centre to the value
(2px radius) and a whisker for the 95% interval with 8px end caps at 60% opacity.
- **Clear:** solid fill in Favoured Blue or Unfavoured Red.
- **Lean:** the same shape outlined (1.5px inset) in the direction's colour, with no
  fill.
- Paired with a text tag beside the value: "Clear" in the ink colour, "Lean" in Muted.

### Build Panel
A Sunken panel (`panel`, 6px radius) holding a typical decklist in two columns
(min 300px each). Lines that are decisions within the build get a 2px Ink Secondary
left edge and a bold name; copy counts sit right-aligned in tabular figures.

### Filter Sheet
A bottom sheet on phones (12px top radius, safe-area padding), centred as a dialog
from 600px, with full-width 44px segmented fields and a primary Apply button. The
backdrop is `rgba(10, 12, 15, 0.45)`.

### Card Viewer
Full-screen near-black overlay (`rgba(8, 9, 11, 0.94)`) with the card image at its
true 488:680 ratio on phones; on desktop a 300px peek beside the pointer over a lightly
dimmed page, closing on mouse move or click.

## Do's and Don'ts

### Do:
- **Do** separate sections with a 1px Hairline and space.
- **Do** draw every win rate as a Diverging Bar with its 95% whisker, solid for Clear
  and outlined for Lean.
- **Do** use the Ink versions of blue and red for any text, so text keeps 4.5:1 on
  every surface in both themes.
- **Do** set every column of numbers in tabular figures.
- **Do** keep touch targets at 44px below 1024px (40px for dense card chips).
- **Do** define every new colour as a role token with a dark-theme twin, and check it in
  both themes.

### Don't:
- **Don't** use blue or red in data for anything other than favoured / unfavoured; blue
  outside data is limited to underlined links and the focus ring.
- **Don't** wrap sections in shadowed or bordered cards; shadows are for floating
  layers only (tooltip, card image).
- **Don't** use the serif for numbers, labels or controls.
- **Don't** show a result as Clear by colour alone; the solid-versus-outline mark and
  the text tag must agree.
- **Don't** add font weights beyond 400, 500 and 600, or a third typeface.
