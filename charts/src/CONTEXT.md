# charts/src/

Code of the chart library.

| File | What it does |
|---|---|
| `chart.js` | `compose`: turns a figure function into a chart type returning figure, data table, alt text and CSV; input checks, footer (source, dataset, vintage, nature, breaks), the SVG's role and alt text, the Greek and English chart text; `barLook`, the grammar for bars |
| `dumbbell.js` | `dumbbell`: change between two periods, one row per area sorted by the second value, focus in the accent, the years labelled on the focus' row, grammar on the second value |
| `grammar.js` | `style(nature, status)`: the epistemic grammar (PROPOSAL §7A) as token names: dash, bands, scenario hue, hollow marker, gap |
| `lexis.js` | `lexis`: Lexis surface, rate by single year of age and calendar year, palette classes, cohort diagonals |
| `line.js` | `line`: line chart over time, focus in the accent, comparators neutral, labels on the lines (areas and scenarios named by `spec.labels`); with interval bounds, a fan chart with 95% and 80% bands and a last-observation rule. `seriesMarks` draws one series (segments, scenario start, markers), also for `tiles.js` |
| `map.js` | `choropleth` (rates only, named classification) and `symbols` (proportional circles for counts) on the data product's Greek geometry, with its attribution in the footer |
| `pyramid.js` | `pyramid`: population pyramid by sex and age, with a second profile as an outline |
| `waterfall.js` | `waterfall`: the parts of one area's total in one period as floating bars, then the total from zero; fails unless the parts add up to the total (`spec.parts`, `spec.total`, `spec.tolerance`) |
| `tiles.js` | `tiles`: small multiples of the regions on a grid that recalls the map, over a reference line |
