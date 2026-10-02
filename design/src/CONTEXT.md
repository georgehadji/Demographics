# design/src/

Code of the design package.

| File | What it does |
|---|---|
| `build.js` | Generates `dist/tokens.css` (CSS variables), `dist/tokens.js` (per-mode hex values for chart scales) and Quarto `dist/_brand.yml` / `dist/_brand-dark.yml` from the tokens |
| `format.js` | `formatNumber`: the one number formatter, `Intl.NumberFormat` with the true minus sign |
| `tokens.js` | `resolve`: reads `tokens.json` and flattens it per mode, with print falling back to light |
