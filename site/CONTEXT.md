# site/

Quarto website (ADR 0005, layer L6): it reads the data product and computes nothing. Most pages are generated before each render from the data product and `catalog.json` (`src/pages.js`, not committed). Values and charts come in only through the shortcodes `{{< fact name geo period [sex] [age] >}}` and `{{< chart spec.json >}}`, which run `src/cli.js` on the data product in `$KOHORTES_DATA` (`grpop-build --out`). A value that is missing, or whose file is not in the manifest with its sha256, stops the render. The `Build` workflow renders it after building the product; locally: `npm ci` in `design/`, `charts/` and here, then `KOHORTES_DATA=<product dir> quarto render`.

| File | What it does |
|---|---|
| `_quarto.yml` | Quarto project: website, Greek, menu, pre-render steps (brand files, generated pages), the shortcodes, the pages to render |
| `_tier.md` | The review-tier notice every page includes |
| `_quarto-wrong.yml` | Profile `wrong`: adds the deliberately wrong pages of `test/` to the render list, for the `Build` workflow |
| `catalog.json` | Page text of the generated pages: Greek title, data product file, sex and age of each indicator page and an optional note on how to read it; the areas compared and their labels; the home page's indicators; the geometry whose regions get a page and the tile layout; the projection files and the Greek name of each scenario |
| `errata.qmd` | Errata: every correction with its date (none yet) |
| `kohortes.lua` | The `fact` and `chart` shortcodes: run `src/cli.js`, and fail the render when it fails |
| `package-lock.json` | Locked dependency tree for `npm ci` |
| `package.json` | Package manifest: script `test`; d3-dsv (CSV), js-yaml (definitions and registry), jsdom (charts drawn at render time); Playwright and axe for `test/axe.spec.js` |
| `playwright.config.js` | Runs `test/*.spec.js` (axe) on the rendered `_site` |
| `src` | The gateway to the data product: see `src/CONTEXT.md` |
| `styles.css` | Shows each chart in the mode (light or dark) the page is in |
| `test` | Unit tests and the deliberately wrong pages: see `test/CONTEXT.md` |
