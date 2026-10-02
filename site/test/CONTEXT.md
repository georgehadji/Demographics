# site/test/

| File | What it does |
|---|---|
| `missing.qmd` | Deliberately wrong page: asks for a value the data product lacks; the `Build` workflow checks that its render fails |
| `product.test.js` | The gateway on a minimal product written at test time: formatting and source, provisional and projected notes, missing values, files outside the manifest or with a wrong sha256, rows without a source, the chart output |
| `unprovenanced.qmd` | Deliberately wrong page: asks for a value from a file outside the manifest; the `Build` workflow checks that its render fails |
