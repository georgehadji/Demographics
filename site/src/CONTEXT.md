# site/src/

| File | What it does |
|---|---|
| `cli.js` | Command line the shortcodes call (`fact`, `chart`), the pre-render steps (`brand`, writes `_brand/` from `design/tokens.json`; `pages`, writes the generated pages) and the link check (`links`); exits non-zero with the reason on any error |
| `links.js` | `brokenLinks`: every local href and src in `_site` that points to no file |
| `pages.js` | The pages made from the data product before each render: one per indicator of `catalog.json` with its chart spec (and, where a regional series exists, a map of the latest period beside the tile grid), the indicator list, one per region of the map geometry (named by GISCO) against Greece, the regions list, projections (EUROPOP2025 with named scenarios, the UN WPP fan), the home page, definitions (from `definitions.yaml`), sources (from the registry) and AI use (from `AI_USE.md`). Shortcodes only, never values |
| `product.js` | `load` checks a data product file against `manifest.json` and its rows for provenance; `geometry` reads a map geometry the same way; `decimals`, a derived indicator's precision from the manifest, which `fact` and `chart` format to; `chart` takes a spec's geometry (a product file) and layout (a `data/reference` table) by name; `fact` formats one value with its source; `chart` draws a `charts/` type in light and dark with its table and CSV |
