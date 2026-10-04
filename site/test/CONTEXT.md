# site/test/

| File | What it does |
|---|---|
| `axe.spec.js` | Playwright + axe (WCAG 2.2 A/AA) on one rendered page of each kind, light and dark; run by the `Build` workflow after the render |
| `missing.qmd` | Deliberately wrong page: asks for a value the data product lacks; the `Build` workflow checks that its render fails |
| `product.test.js` | The gateway on a minimal product written at test time: formatting and source, provisional and projected notes, missing values, files outside the manifest or with a wrong sha256, rows without a source, the chart output |
| `pages.test.js` | The generated pages on a minimal product: latest period, facts as shortcodes only, areas without data left out, definitions and sources; the link check on a hand-made `_site` |
| `unprovenanced.qmd` | Deliberately wrong page: asks for a value from a file outside the manifest; the `Build` workflow checks that its render fails |
