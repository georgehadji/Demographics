# site/

Quarto website (ADR 0005, layer L6): it reads the data product and computes nothing. Values and charts come in only through the shortcodes `{{< fact name geo period [sex] [age] >}}` and `{{< chart spec.json >}}`, which run `src/cli.js` on the data product in `$KOHORTES_DATA` (`grpop-build --out`). A value that is missing, or whose file is not in the manifest with its sha256, stops the render. The `Build` workflow renders it after building the product; locally: `npm ci` in `design/`, `charts/` and here, then `KOHORTES_DATA=<product dir> quarto render`.

| File | What it does |
|---|---|
| `_quarto.yml` | Quarto project: website, Greek, brand files made by the pre-render step, the shortcodes, the pages to render |
| `fertility.json` | Chart spec of the sample page: total fertility rate, Greece and the EU-27 |
| `index.qmd` | Sample page with its review tier, two values and a chart from the data product |
| `kohortes.lua` | The `fact` and `chart` shortcodes: run `src/cli.js`, and fail the render when it fails |
| `package-lock.json` | Locked dependency tree for `npm ci` |
| `package.json` | Package manifest: script `test`; d3-dsv (CSV) and jsdom (charts drawn at render time) |
| `src` | The gateway to the data product: see `src/CONTEXT.md` |
| `styles.css` | Shows each chart in the mode (light or dark) the page is in |
| `test` | Unit tests and the deliberately wrong pages: see `test/CONTEXT.md` |
