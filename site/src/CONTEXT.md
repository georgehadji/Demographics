# site/src/

| File | What it does |
|---|---|
| `cli.js` | Command line the shortcodes call (`fact`, `chart`) and the pre-render step (`brand`, writes `_brand/` from `design/tokens.json`); exits non-zero with the reason on any error |
| `product.js` | `load` checks a data product file against `manifest.json` and its rows for provenance; `fact` formats one value with its source; `chart` draws a `charts/` type in light and dark with its table and CSV |
