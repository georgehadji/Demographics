# charts/test/

Unit tests, run by `npm test`.

| File | What it does |
|---|---|
| `dumbbell.test.js` | The dumbbell: sorting, accent and comparators, year labels, hollow and dashed second values, alt text, input errors |
| `grammar.test.js` | The grammar for every `nature` × `status`; its vocabulary matches `pipeline/src/grpop/provenance.py`; every locale labels every nature, status, sex and interval bound; Greek labels for every unit of `definitions.yaml` |
| `lexis.test.js` | The Lexis surface: cells, palette classes, cohort lines, provisional outline, projection rule, input errors |
| `line.test.js` | The line chart and the composite: colours, dashes, gaps (focus only at breaks), scenario start, hollow markers, label dodging, fan bands, last observation, table, alt text, CSV, input errors |
| `map.test.js` | Choropleth and proportional symbols: palette, classification, attribution, focus outline, ring winding, grammar, rates vs counts, size key, alt text, input errors |
| `pyramid.test.js` | The pyramid: sides, outline comparison, grammar on bars, alt text, input errors |
| `rows.js` | Shared by the tests: a jsdom document, the tokens, a hand-written observation row and selectors for Plot's mark groups (without the invisible tooltip points) |
| `waterfall.test.js` | The waterfall: floating parts and total, grammar, alt text, measure column, the sum check and its tolerance, input errors |
| `tip.test.js` | Tooltips: the text of one, and every chart type of the gallery giving each value one built from its row |
| `tiles.test.js` | The tile grid: the layout covers every Greek NUTS 2 region once, accent and reference lines, labels, input errors |
