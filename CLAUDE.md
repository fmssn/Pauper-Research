# Pauper-Research

Metagame, matchup and card statistics for MTG Pauper. See README.md for usage.

## Keep the methods page current

The dashboard has a **Methods** page (`#methods`, the `methodsView` section of
`pauper_research/dashboard_template.html`) that documents every statistic shown,
with LaTeX formulas rendered by MathJax.

Whenever you add or change a statistic, interval, model, weighting or display
threshold, update that page in the same change:

- Add or edit the section with the formula in TeX (`\( … \)` inline, `\[ … \]`
  display) and a plain-language explanation of every symbol.
- Never hard-code a setting in the text. Expose it from Python (`build_data`
  → `thresholds` or `methods`) or a JS constant, show it with
  `<b data-k="name"></b>` and fill it in `renderMethods`.
  `tests/test_pipeline.py::test_methods_page_in_sync` fails if a `data-k` has no value.
- Keep the README's "How the numbers are computed" and "Pilot skill" sections
  consistent with the page.

## Checks

- `python -m pytest -q`
- After dashboard changes, build it (`python -m pauper_research dashboard`) and
  look at it in a browser, in both light and dark themes.
