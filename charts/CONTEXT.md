# charts/

Node package with the chart library (ADR 0005): ES modules on Observable Plot. Every chart is `f(rows, spec, {tokens, document})` and returns `{figure, table, alt, csv}`. Rows are observations of the data product; `tokens` are one mode of `design/dist/tokens.js`. `npm test` runs the unit tests and `npm run visual` the Playwright screenshots and axe checks (install `design/` first: charts imports its tokens and number formatter).

| File | What it does |
|---|---|
| `package-lock.json` | Locked dependency tree for `npm ci` |
| `package.json` | Package manifest: scripts `test` and `visual`, Observable Plot; jsdom, Playwright and axe for tests |
| `playwright.config.js` | Playwright settings for the visual tests: baselines per platform in `visual/snapshots`, optional installed Chrome (`PW_CHANNEL=chrome`) |
| `src` | The grammar, the composite and the chart types: see `src/CONTEXT.md` |
| `test` | Unit tests run by `node --test`: see `test/CONTEXT.md` |
| `visual` | Visual regression and accessibility tests: see `visual/CONTEXT.md` |
