# charts/

Node package with the chart library (ADR 0005): ES modules on Observable Plot. Every chart is `f(rows, spec, {tokens, document})` and returns `{figure, table, alt, csv}`. Rows are observations of the data product; `tokens` are one mode of `design/dist/tokens.js`. `npm test` runs the tests (install `design/` first: charts imports its tokens and number formatter).

| File | What it does |
|---|---|
| `package-lock.json` | Locked dependency tree for `npm ci` |
| `package.json` | Package manifest: script `test`, Observable Plot, jsdom for tests |
| `src` | The grammar, the composite and the chart types: see `src/CONTEXT.md` |
| `test` | Tests run by `node --test`: see `test/CONTEXT.md` |
