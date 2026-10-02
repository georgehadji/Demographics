# design/test/

Validators, run by `npm test`.

| File | What it does |
|---|---|
| `build.test.js` | Every token appears in the generated CSS, JS module and brand files |
| `format.test.js` | Greek and English number formats and the true minus sign |
| `tokens.test.js` | sRGB gamut, WCAG 2.2 AA contrast per mode, line colours apart in lightness and under protan/deutan/tritan simulation, map classes away from the accent, palette lightness order, neutral diverging centre, band visibility, boundary contrast |
