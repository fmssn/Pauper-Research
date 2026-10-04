---
target: pauper_research/dashboard_template.html
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:/home/user/Pauper-Research/pauper_research/dashboard_template.html"
target_fingerprint: "sha256:6cb433e23b8fcfdc581ea3c2c706fb91e02dcfbc4dc6776f6c6d07061e25d676"
target_path: /home/user/Pauper-Research/pauper_research/dashboard_template.html
timestamp: 2026-10-04T21-36-33Z
slug: pauper-research-dashboard-template-html
---
Method: dual-agent (A: design review sub-agent, B: detector sub-agent). Fonts and MathJax were blocked in the sandbox, so screenshots used fallback fonts and raw TeX; neither was scored against the design.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Phone filter chip "90d · All" omits pilot-skill correction, which changes every number |
| 2 | Match System / Real World | 3 | "pts against the other lists", lists vs matches: statistician terms without a gloss |
| 3 | User Control and Freedom | 3 | Routing, breadcrumbs, back and "see it from the other side" all work; sheet has no reset |
| 4 | Consistency and Standards | 2 | Outline means Lean on bars but Clear on opponent chips; section order changes by width |
| 5 | Error Prevention | 2 | Lean card/build effects get the boldest numbers (Highway Robbery +14 on 21 matches) |
| 6 | Recognition Rather Than Recall | 3 | Bar scale only under the last row; legend far from the bars |
| 7 | Flexibility and Efficiency | 3 | "/" search and sorts; no deck comparison or custom field |
| 8 | Aesthetic and Minimalist Design | 2 | Deck page 3,684px desktop / 5,392px phone, over half "No clear difference" rows |
| 9 | Error Recovery | 2 | MathJax failure leaves raw TeX with only a footnote |
| 10 | Help and Documentation | 4 | Methods page: short version, TOC, live settings, in-place links |
| **Total** | | **27/40** | **Acceptable** |

## Design Specificity Verdict
Authored for this product: mana pips, serif only for the subject, Clear/Lean language, the diverging bar with whisker, source-mix line, decisions phrased as deckbuilding questions. Missed opportunity: no verdict on whether to register the deck.
Detector: template 129 findings (110 low-contrast false positives from pairing dark tokens with light paper), built page 18 advisory/warning findings. Real: .howto list ~136-char lines (no max-width); undocumented viewer colours #1b1d21, #9cc4f2, rgba(17,19,23,.92) and radii 24px/8px; 8px mana-pip letters. cramped-padding on .bar/dialogs is a false positive.

## Priority Issues
- [P1] Lean results carry the most visual weight in cards and builds. Fix: mute Lean values, fold Lean card/build rows under "Could go either way", collapse all-Lean decisions into one "stock list is fine" line. distill, clarify.
- [P1] No register-or-not verdict on the deck page. Fix: field-weighted expected win rate with interval, plus worst common matchup. shape.
- [P2] Outline means Lean on bars but Clear on opponent chips (template L606 vs L749, L1622). Fix: Clear chips get tinted fill or tag; outline = Lean everywhere. clarify.
- [P2] Phone top bar truncates deck name and date; filter chip hides pilot correction. Fix: drop date below 420px, full-width title, chip "90d · All · Adj". adapt.
- [P3] Bar scale only under the last row; sidebar mini bars too small for Clear vs Lean; .howto lines ~136 chars. polish.

## Persona Red Flags
Alex: no compare, no custom field, chart labels collide at 3-5% share. Sam: focus ring merges with ink-filled pressed segment; raw TeX read aloud if MathJax fails; no in-page jump links on a 5,000px page. Casey: sideboard cards are below the whole Builds block; CDN fonts/MathJax degrade on venue Wi-Fi. RCQ grinder: no field-weighted answer; Lean +14 may push a bad 75 change.

## Minor Observations
Ragged pip column in matchup rows; hover state sticks on clicked sidebar row; interval wraps under 48% on phones; "Uncorrected win rate" easy to miss; 1440px matchup page leaves ~40% empty; fonts and MathJax not self-contained.

## Questions to Consider
- If almost every build and card result is Lean, should the deck page show none by default?
- Should the home screen be "against the current field, these decks clearly win" rather than the deck list?
- Should pilot correction be on by default when users quote these numbers to friends?
