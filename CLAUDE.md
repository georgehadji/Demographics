# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Start every task with [`CONTEXT.md`](CONTEXT.md):** what the project does, a map of every folder, and a link to each folder's `CONTEXT.md`, which describes every file in it. Find files there before searching. When you add, remove, rename or repurpose a file, update its folder's `CONTEXT.md` in the same change (`pipeline/tests/test_context.py` enforces it). Other agents enter through `AGENTS.md`, which points here.

**Κοόρτες / Kohortes** (open demographic analysis of Greece; see ADR 0003): a non-commercial research and publication project on the demography of Greece. Goal: public credibility.
Claude builds everything (code, analysis, text, design). The responsible editor is **Georgios-Chrysovalantis Chatzivantsidis**, who approves every publication.
There is **no external reviewer yet**. Publications must carry their review tier (PROPOSAL §1B) and must never be presented as reviewed. See `AI_USE.md`.
Licences: code MIT, content and derived data CC BY 4.0, subject to the source terms.
The authoritative plan is `docs/PROPOSAL.md` (Greek). Decisions live in `docs/decisions/`. Read both before starting a new phase.

## Non-negotiable rules

- **Single source of truth ([ADR 0006](docs/decisions/0006-single-source-of-truth.md)).** Every fact has exactly one home (the table in ADR 0006). Code reads it and text links to it; never copy values (codes, URLs, numbers, licence terms, units, colours) into a second place. Derived files are generated, never hand-edited. When you find a duplicate, remove it or add it to step A5 of `docs/IMPLEMENTATION-PLAN.md`.
- **No number without provenance.** Every value passes the contract in `pipeline/src/grpop/provenance.py`, which defines the fields, the `nature`/`status` vocabulary and the observation key. `retrieved_at` is set by the pipeline, never by hand. Official ≠ verified: ELSTAT net migration is an `official_estimate`.
- **Never type a number into prose.** Publications are Quarto documents with inline computed values.
- **Never write a citation from memory.** Every cited work is a row of `data/bibliography/references.csv`; `grpop-bib` (the `Bibliography` workflow) resolves each DOI and fails unless title and authors match.
- Never overwrite a source value silently. Snapshots are immutable, and revisions are stored as history.
- Every `derived` indicator that an official source also publishes must match it within rounding, enforced by a test.
- Every model must reproduce a published result before it produces a new one (e.g. the cohort-component engine must reproduce the EUROPOP2025 baseline).
- Scenarios are labelled as mathematical consequences of assumptions, never as forecasts or policy effects.
- Migration terminology: distinguish foreign citizens, foreign-born, and migration flows vs stocks. Never use ethnic framing.
- In user-facing text, mark claims as VERIFIED / INFERENCE / HYPOTHESIS / UNKNOWN where certainty matters.

## Stack and architecture

Decided in [ADR 0001](docs/decisions/0001-project-scope-and-stack.md) (scope, static-only) and [ADR 0005](docs/decisions/0005-software-architecture.md) (layers, patterns per module, Quarto for site and reports). The stack table is PROPOSAL §9.1; what LLMs may and may not do is PROPOSAL §8. Read them before changing the stack; do not restate them here.

## Design system (PROPOSAL §7A)

- The chart title states the finding. The footer states source, dataset, vintage and `nature`.
- Epistemic grammar: solid = observed/estimate/derived; dashed + bands = projected; dotted in a different hue family = scenario; hollow marker = provisional; break in series = footnote mark and note, plus a line gap in the focus' line only (comparators such as the EU-27 inherit every member state's break).
- Greece gets the single accent colour, comparators are neutral, labels go directly on the lines.
- Choropleths show rates only and are paired with a cartogram or proportional symbols.
- Greek: no accented all-caps; locale number formatting via `Intl.NumberFormat` (`10.372.335`, `−0,03%`); true minus sign.
- Every chart has a data-table view, a CSV download and data-derived alt text. Target WCAG 2.2 AA.
- Playwright visual regression in light/dark/print. Inspect screenshots before every release.

## Working in `pipeline/` (Python package `grpop`)

Current state: Phase 1 closed on 2026-10-03 (PROPOSAL §10); Phase 2 (approved 2026-10-03) is in progress, in parts Δ–Ζ of `docs/IMPLEMENTATION-PLAN.md`; the code is `pipeline/`, `design/`, `charts/` and the `site/` skeleton. The reports are planned (ADR 0005) and don't exist yet.

- Before every push, run `cd pipeline && uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy` and make sure it passes. CI (`.github/workflows/ci.yml`) runs the same steps with `uv sync --locked`; lint settings are in `pyproject.toml`.
- To run a single test: `uv run pytest tests/test_provenance.py::test_duplicate_key_fails`.
- `src/grpop/provenance.py` is the provenance contract. Every published value must pass `validate_observations`. The schema is strict and never coerces types: read the module before producing observations. Breakdowns by sex and age are the `sex` and `age` columns, never separate metrics; totals are explicit values, not null. A break in series is the `break_in_series` column, independent of `status`. An uncertainty interval bound is its own row with `interval` set (ADR 0007); the central value has `interval` null. `definition_id`, `metric` and `unit` must match `definitions.yaml`.
- `src/grpop/definitions.yaml` defines every `definition_id` (meaning, unit, version). Parsers and indicators read metric and unit from it via `get_definition`; they never type them.
- Parsers take source metadata from the registry via `get_source(<id>)`, not from constants. Example: `src/grpop/parse/elstat_xlsx.py`.
- `src/grpop/indicators.py`: each indicator is one `Indicator` in `INDICATORS` (definition, input series, Polars formula, official counterpart, rounding). `tests/test_indicators.py` generates the acceptance tests from it: our value must match the official one within its rounding. Official series published unchanged (population, natural change, life expectancy, …) are `Series` in `SERIES`. All inputs of one indicator must come from one source. A new indicator or series needs recorded fixtures for its sources in that test's `RECORDED`. A difference from the official value is explained in one of two ways. Either a `corroboration` indicator computes the same value from another Eurostat table, which the check verifies cell by cell; or, where no table can, the cells go in `known_differences` with the evidence in a comment. Regional entries (`*_regional`) cover Greece and its regions only (`Series.geo_prefix`). `indicators.check` compares every country and year the build reads. It fails on an unexplained difference, and on a listed one that was compared but has gone away or is now corroborated.
- `src/grpop/build.py` (`uv run grpop-build --store DIR --out DIR`) builds the data product from the latest snapshot of each source: every entry of `INDICATORS` and `SERIES` is one step of `STEPS`, validated and written as `<name>.parquet` and `<name>.csv` with its rows in key order. The map geometry (`GEOMETRY`, from `parse/gisco.py`) is `<name>.geojson`, carrying its source, licence and attribution: GISCO's terms are non-commercial, so it is not CC BY. `manifest.json` lists each file's sha256, its sources, the hash of its inputs and, for a derived indicator, the official value's `decimals` (snapshots, code, reference data, Polars version); a step whose inputs and files are unchanged is not rebuilt. Two builds from the same inputs must give the same bytes (`tests/test_build.py`). The `Build` workflow runs it twice from scratch on the `snapshots` release after each Ingest run and on every push that changes the code or the reference data.
- `src/grpop/groups.py`: peer groups (PROPOSAL §6), members in `data/reference/peer_groups.csv` with a version per group. A change of members bumps the version. The build adds the EU-27 median (`EU27_2020_MEDIAN`, `derived`, only where all 27 have a value) to every national step whose unit is not persons, and its `peer_groups` step fails if a member has no population or the very-low-fertility list no longer follows its rule.
- `src/grpop/projections.py`: EUROPOP2025 (`proj_25np`). The baseline is `projected`; each sensitivity test is a `scenario` with `scenario_id` `europop2025_<assumption>` (ADR 0008). The baseline's base-year totals must equal `demo_pjan` except the countries in `KNOWN_BASE_DIFFERENCES`, each with its evidence. UN WPP 2024 (`parse/un_wpp.py`, `population_1jul@v1`) is the probabilistic workbook: the median and the 80/95% bounds as `interval` rows; `wpp_checked` compares the medians with `demo_pjan` (1 July against the mean of two 1 January values) within `WPP_TOLERANCE`, except the areas listed with their reason. The Ingest workflow downloads Phase 1-2 sources (`--phase 2`), Eurostat datasets and files with `ingest` set (`geojson`, `xlsx`).
- `src/grpop/publish.py` (`grpop-publish`, the `Publish` workflow, by hand): a data release is a zip of the product (only files whose sources allow commercial reuse), `manifest.json`, `SOURCES.md` from the registry, `snapshots.txt` and the newest `publish/CHANGELOG.md` entry, deposited on Zenodo for the DOI. `grpop-build --pin snapshots.txt` rebuilds a release from the snapshots it lists. Run the `sandbox` target before `zenodo`; a release is public and its DOI permanent. A later version passes the concept record id from `CITATION.cff` as `concept`.
- `src/grpop/harmonize.py`: Greek NUTS codes and boundaries are the same in NUTS 2013–2024. Some Eurostat tables give 2011 for EL5, EL6 and their regions only in NUTS 2010 codes; `recode_nuts2010` maps the NUTS 2 ones (code change only, `data/reference/nuts2010_el_recodes.csv`) and drops the rest. `Series.read` applies it and then rejects any other non-NUTS 2024 Greek code (`data/reference/nuts2024_el.csv`). `hierarchy_gaps` checks that each level adds up to its parent. `age_gaps` checks that the age groups below each open group (85+, 90+) plus that group and unknown age add up to the total; the build applies both checks to the steps in `build.ADDS_UP` (`population_by_age_group_regional`, five-year groups of Greece and its NUTS 1-3 regions), except differences within `build.KNOWN_GAPS` (per period and sex, with its evidence).
- `src/grpop/parse/eurostat.py` turns one metric of a Eurostat snapshot into observations. It is the only place Eurostat codes are translated: flags to `status`/`nature`/`break_in_series`, sex and age codes to the contract. Unknown flags or codes raise.
- `src/grpop/snapshots.py` stores raw downloads by sha256 with an append-only `manifest.jsonl`. Parsers read bytes from it, never from the network; `retrieved_at` comes from the snapshot.
- `src/grpop/sources/eurostat.py` (`grpop-ingest`) downloads whole Eurostat datasets (the probe URL without filters), and the file of each registry entry with `ingest` set (its probe URL, e.g. GISCO GeoJSON), into the store, with backoff on network errors, 429 and 5xx. The `Ingest` workflow runs it weekly and keeps the store as assets of the `snapshots` release: objects by sha256 plus one `manifest-<UTC time>.jsonl` per run. Nothing there is overwritten or deleted.
- `src/grpop/parse/jsonstat.py` turns Eurostat JSON-stat into long format: one string column per dimension, plus `value` and the source `flag` (e.g. `p` = provisional). Cells the source did not publish are kept as null rows, so "not published" stays distinct from "not requested".
- `src/grpop/sources/registry.yaml` lists every source, validated by `registry.py`. Each licence is written once under `licences` and referenced by key from each source; an unknown or unused key is an error. The verification flow:
  1. The `Source probe` workflow runs `grpop-probe` weekly, on demand, and whenever `registry.yaml` or `probe.py` changes.
  2. It uploads `probe-report.md/json` as an artifact.
  3. The probe never edits the registry. A person or Claude reads the report and records it.
  4. Set an entry to `verified` only with `checked_at` and `evidence` (the run id and the observed result) taken from that report.
- Test fixtures that were hand-written rather than recorded from a real response must say so in a `_comment` field.

## Working in `design/` (Node package, design tokens)

- `tokens.json` is the only home of design values (ADR 0006): colours in OKLCH per mode (`light`, `dark`, `print`; print falls back to light), palettes, stroke widths and dash patterns of the epistemic grammar, fonts, spacing. Change a value there, never in a generated file.
- `npm run build` generates `dist/` (not committed): `tokens.css` (CSS variables, dark mode under `prefers-color-scheme` and `[data-theme]`, print under `@media print`), `tokens.js` (per-mode values with colours as hex, for chart scales) and Quarto's `_brand.yml` / `_brand-dark.yml`.
- `npm test` (`node --test`) runs the validators in `test/`: every colour inside the sRGB gamut; WCAG 2.2 AA contrast in every mode; accent, comparator and scenario apart in lightness (grayscale) and in colour under protan/deutan/tritan simulation; no map class close to the accent; palettes monotone in lightness and distinct step by step under each simulation, with a neutral diverging centre; uncertainty bands visible; region boundaries at 3:1 against faint map classes; the number format. CI runs it on every push.
- `src/format.js` `formatNumber` is the one number formatter: `Intl.NumberFormat` plus the true minus sign. Never format a number another way.

## Working in `charts/` (Node package, chart library)

- Every chart type is `compose(figure)` from `src/chart.js`: `f(rows, spec, {tokens, document})` returns `{figure, table, alt, csv}`. Rows are observations of the data product, checked on entry; `spec.title` states the finding; the footer is built from the rows. `tokens` is one mode of `design/dist/tokens.js`.
- `src/grammar.js` `style(nature, status)` is the only place the epistemic grammar lives. It returns token names, never values. `test/grammar.test.js` checks it for every `nature` × `status` and against the vocabularies of `provenance.py`.
- Chart types: `line` (with interval bounds it is the fan chart), `pyramid`, `lexis`, `dumbbell` (two periods), `waterfall` (parts that must add up to their total), `tiles` (layout in `data/reference/el_nuts2_tiles.csv`), and the maps `choropleth` (rates only) and `symbols` (counts), which take the data product's geometry as `spec.geometry` and put its attribution in every footer. Interval bounds (ADR 0007) are drawn as bands, never as lines, labels or alt text.
- Numbers go through `design/src/format.js`; colours, widths and dashes come from `tokens`. Install `design/` (`npm ci`) before running `npm test` here.
- `npm run visual` runs `visual/charts.spec.js`: every type in light, dark and print against baseline screenshots, plus axe (WCAG 2.2 A/AA). Committed baselines are Linux only, made by the `Visual` workflow run with `update`; locally set `PW_CHANNEL=chrome` and look at the screenshots, which git ignores. Look at the Linux baselines before every release.

## Working in `site/` (Quarto website)

- The site reads the data product and computes nothing (ADR 0005, L6). Values go in only as `{{< fact name geo period [sex] [age] >}}`, where `name` is a data product file (a step of `build.STEPS`); charts only as `{{< chart spec.json >}}`, a JSON spec of a `charts/` type plus `data` and `geo`. Both run `src/cli.js` on `$KOHORTES_DATA`. Every chart carries a source panel built from its rows, and every drawn value a tooltip (an SVG title, no script); the keyboard reaches the same fields through the panel and the data table.
- `src/product.js` is the gateway: a file must be in `manifest.json` with a matching sha256, its rows must carry their provenance, and a `fact` must match exactly one central value. Any failure stops the render; never work around it in a page.
- Pages are generated before each render (`src/pages.js`, pre-render, not committed) from the data product and `catalog.json`: one per indicator (with the regions where a regional series exists: a rate as a choropleth beside the tile grid, a count as proportional symbols) and per region (named by GISCO), projections, the home page, definitions, sources, AI use. They contain shortcodes only; the period of each fact is the latest one in the data. Publishing is the `Build` workflow run by hand on main with `deploy` ticked, only on the editor's explicit yes.
- `npm test` runs the gateway's tests. The `Build` workflow renders the site from the product it just built and checks that `test/missing.qmd` and `test/unprovenanced.qmd` fail. Quarto needs the brand files inside the project: the pre-render step writes `_brand/` from `design/tokens.json` (not committed).

## Environment notes

- The cloud dev environment's network policy currently blocks the data-source hosts (the list in `README.md`, checked against the registry by `tests/test_docs.py`). Only package registries (PyPI, npm) are reachable. Use test fixtures locally and run real ingestion in GitHub Actions until the owner allows those domains.
- Cloud environment only: Chromium is preinstalled for Playwright (`/opt/pw-browsers`). Do not run `playwright install`.
- Windows: Windows has no IANA timezone database. Keep the `tzdata; sys_platform == 'win32'` dependency, because without it the UTC `retrieved_at` column panics in polars (`ZoneInfoNotFoundError: UTC`).
