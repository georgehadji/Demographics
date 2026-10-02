# design/

Node package with the design tokens (ADR 0006: the only home of design values) and their validators. `npm test` validates, `npm run build` writes `dist/` (not committed).

| File | What it does |
|---|---|
| `package-lock.json` | Locked dependency tree for `npm ci` |
| `package.json` | Package manifest: scripts `build` and `test`, the one dependency (`culori`) |
| `src` | Generators and the number formatter: see `src/CONTEXT.md` |
| `test` | Validators run by `node --test`: see `test/CONTEXT.md` |
| `tokens.json` | The design tokens: OKLCH colours per mode (light, dark, print), sequential and diverging palettes, stroke widths and dash patterns of the epistemic grammar, font, spacing |
