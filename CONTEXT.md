# CONTEXT.md: project map

Kohortes (Κοόρτες) is an open, non-commercial research and publication project on the demography of Greece. A Python pipeline turns official statistics (mainly Eurostat) into a validated data product with full provenance. A design system, a chart library and a Quarto site (later also reports) present it. The plan is [`docs/PROPOSAL.md`](docs/PROPOSAL.md); the order of work is [`docs/IMPLEMENTATION-PLAN.md`](docs/IMPLEMENTATION-PLAN.md); the working rules are [`CLAUDE.md`](CLAUDE.md).

Every tracked folder that holds files has its own `CONTEXT.md`, with one line per file. This file maps the folders and the root files. `pipeline/tests/test_context.py` fails when a file is missing from its folder's map, or a map lists a file that does not exist.

## Folder map

```
.
├── .github/scripts/        shell steps shared by workflows
├── .github/workflows/      CI and scheduled workflows
├── charts/                 chart library on Observable Plot (Node)
│   ├── src/
│   ├── test/
│   └── visual/         screenshot and accessibility tests
├── data/bibliography/      the cited works: key, DOI, expected title and authors
├── data/reference/         small reference CSVs (NUTS codes and recodes, ELSTAT labels)
├── design/                 design tokens, generators and validators (Node)
│   ├── src/
│   └── test/
├── docs/                   proposal, plan, review, landscape scan
│   ├── decisions/          ADRs
│   └── spikes/             time-boxed investigations
├── pipeline/               Python package grpop: sources → snapshots → observations → indicators → data product
│   ├── src/grpop/
│   │   ├── parse/
│   │   └── sources/
│   └── tests/
│       └── fixtures/       responses recorded from the live sources
├── publish/                data releases: changelog (Zenodo DOI via the Publish workflow)
└── site/                   Quarto website: reads the data product through fact() and chart()
    ├── src/
    └── test/
```

| Folder | Map |
|---|---|
| `.github/scripts` | [`.github/scripts/CONTEXT.md`](.github/scripts/CONTEXT.md) |
| `.github/workflows` | [`.github/workflows/CONTEXT.md`](.github/workflows/CONTEXT.md) |
| `charts` | [`charts/CONTEXT.md`](charts/CONTEXT.md) |
| `charts/src` | [`charts/src/CONTEXT.md`](charts/src/CONTEXT.md) |
| `charts/test` | [`charts/test/CONTEXT.md`](charts/test/CONTEXT.md) |
| `charts/visual` | [`charts/visual/CONTEXT.md`](charts/visual/CONTEXT.md) |
| `charts/visual/snapshots` | [`charts/visual/snapshots/CONTEXT.md`](charts/visual/snapshots/CONTEXT.md) |
| `data/bibliography` | [`data/bibliography/CONTEXT.md`](data/bibliography/CONTEXT.md) |
| `data/reference` | [`data/reference/CONTEXT.md`](data/reference/CONTEXT.md) |
| `design` | [`design/CONTEXT.md`](design/CONTEXT.md) |
| `design/src` | [`design/src/CONTEXT.md`](design/src/CONTEXT.md) |
| `design/test` | [`design/test/CONTEXT.md`](design/test/CONTEXT.md) |
| `docs` | [`docs/CONTEXT.md`](docs/CONTEXT.md) |
| `docs/decisions` | [`docs/decisions/CONTEXT.md`](docs/decisions/CONTEXT.md) |
| `docs/spikes` | [`docs/spikes/CONTEXT.md`](docs/spikes/CONTEXT.md) |
| `pipeline` | [`pipeline/CONTEXT.md`](pipeline/CONTEXT.md) |
| `pipeline/src/grpop` | [`pipeline/src/grpop/CONTEXT.md`](pipeline/src/grpop/CONTEXT.md) |
| `pipeline/src/grpop/parse` | [`pipeline/src/grpop/parse/CONTEXT.md`](pipeline/src/grpop/parse/CONTEXT.md) |
| `pipeline/src/grpop/sources` | [`pipeline/src/grpop/sources/CONTEXT.md`](pipeline/src/grpop/sources/CONTEXT.md) |
| `pipeline/tests` | [`pipeline/tests/CONTEXT.md`](pipeline/tests/CONTEXT.md) |
| `pipeline/tests/fixtures` | [`pipeline/tests/fixtures/CONTEXT.md`](pipeline/tests/fixtures/CONTEXT.md) |
| `publish` | [`publish/CONTEXT.md`](publish/CONTEXT.md) |
| `site` | [`site/CONTEXT.md`](site/CONTEXT.md) |
| `site/src` | [`site/src/CONTEXT.md`](site/src/CONTEXT.md) |
| `site/test` | [`site/test/CONTEXT.md`](site/test/CONTEXT.md) |

## Root files

| File | What it does |
|---|---|
| `.gitignore` | Build outputs, caches, virtual environments and generated files kept out of git |
| `AGENTS.md` | Entry point for coding agents other than Claude Code: read this map, follow `CLAUDE.md` |
| `AI_USE.md` | How AI is used in the project and the review tier every publication must state |
| `CITATION.cff` | How to cite the project |
| `CLAUDE.md` | Working rules for Claude Code (non-negotiable rules, design system, how to work in each package) |
| `LICENSE` | MIT licence for the code |
| `LICENSE-CONTENT.md` | CC BY 4.0 for text, charts and derived data, subject to each source's terms |
| `README.md` | Public overview in Greek: status, structure, required network access, licences |

## Where to find what

| Task | Start at |
|---|---|
| Add or verify a data source | `pipeline/src/grpop/sources/registry.yaml`, then the `Source probe` workflow |
| Define a metric (meaning, unit, version) | `pipeline/src/grpop/definitions.yaml` |
| Add an indicator or official series | `pipeline/src/grpop/indicators.py`, with fixtures in `pipeline/tests/test_indicators.py` |
| Change what a published value must carry | `pipeline/src/grpop/provenance.py` |
| Greek NUTS codes and regional checks | `pipeline/src/grpop/harmonize.py` and `data/reference/` |
| Build the data product | `pipeline/src/grpop/build.py` (`grpop-build`) |
| Change a colour, font, spacing or line style | `design/tokens.json` |
| Draw a chart, or change how nature and status look | `charts/src/` (`grammar.js` for the epistemic grammar) |
| Check how the charts look, or update the screenshots | `charts/visual/` and the `Visual` workflow |
| Format a number for display | `design/src/format.js` |
| Quote a value or show a chart on the site | `site/` (`{{< fact >}}`, `{{< chart >}}`; gateway in `site/src/product.js`) |
| Why something was decided | `docs/decisions/` |
