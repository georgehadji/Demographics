# charts/test/

Unit tests, run by `npm test`.

| File | What it does |
|---|---|
| `grammar.test.js` | The grammar for every `nature` × `status`; its vocabulary matches `pipeline/src/grpop/provenance.py`; every locale labels every nature, status, sex and interval bound |
| `lexis.test.js` | The Lexis surface: cells, palette classes, cohort lines, provisional outline, projection rule, input errors |
| `line.test.js` | The line chart and the composite: colours, dashes, gaps, scenario start, hollow markers, label dodging, fan bands, last observation, table, alt text, CSV, input errors |
| `pyramid.test.js` | The pyramid: sides, outline comparison, grammar on bars, alt text, input errors |
| `rows.js` | Shared by the tests: a jsdom document, the tokens, a hand-written observation row and selectors for Plot's mark groups |
| `tiles.test.js` | The tile grid: the layout covers every Greek NUTS 2 region once, accent and reference lines, labels, input errors |
