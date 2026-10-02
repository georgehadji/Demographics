# charts/visual/

Visual regression and accessibility tests, run by `npm run visual` (Playwright) and by the `Visual` workflow.

| File | What it does |
|---|---|
| `charts.spec.js` | Each chart type in light, dark and print compared with its baseline screenshot, and no WCAG 2.2 A/AA violation found by axe |
| `gallery.js` | Builds the test page for one mode: every chart type with its data table, from hand-written illustrative rows |
| `snapshots` | Baseline screenshots: see `snapshots/CONTEXT.md` |
