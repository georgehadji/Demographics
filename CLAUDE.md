# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Κοόρτες / Kohortes** (open demographic analysis of Greece; see ADR 0003): a non-commercial research and publication project on the demography of Greece. Goal: public credibility.
Claude builds everything (code, analysis, text, design). The responsible editor is **Georgios-Chrysovalantis Chatzivantsidis**, who approves every publication.
There is **no external reviewer yet**. Publications must carry their review tier (PROPOSAL §1B) and must never be presented as reviewed. See `AI_USE.md`.
Licences: code MIT, content and derived data CC BY 4.0, subject to the source terms.
The authoritative plan is `docs/PROPOSAL.md` (Greek). Decisions live in `docs/decisions/`. Read both before starting a new phase.

## Non-negotiable rules

- **No number without provenance.** Every value carries `source`, `dataset_code`, `source_url`, `vintage`, `retrieved_at` (set by the pipeline, never by hand), `unit`, `definition_id`, `geo_code`, `geo_vintage`, `transform_version`, `nature`, `status` (see PROPOSAL §2).
- `nature` ∈ `observed | official_estimate | derived | projected | scenario`; `status` ∈ `provisional | final | revised | break_in_series | not_available`. Official ≠ verified: ELSTAT net migration is an `official_estimate`.
- **Never type a number into prose.** Publications are Quarto documents with inline computed values.
- **Never write a citation from memory.** Every DOI is resolved and matched against title and authors before use.
- Never overwrite a source value silently. Snapshots are immutable, and revisions are stored as history.
- Every `derived` indicator that an official source also publishes must match it within rounding, enforced by a test.
- Every model must reproduce a published result before it produces a new one (e.g. the cohort-component engine must reproduce the EUROPOP2025 baseline).
- Scenarios are labelled as mathematical consequences of assumptions, never as forecasts or policy effects.
- Migration terminology: distinguish foreign citizens, foreign-born, and migration flows vs stocks. Never use ethnic framing.
- In user-facing text, mark claims as VERIFIED / INFERENCE / HYPOTHESIS / UNKNOWN where certainty matters.

## Stack (decided, see ADR 0001)

- Python 3.12+ with `uv`, DuckDB + Parquet, Polars, `pandera`, `pytest`, `hypothesis`, `statsmodels`, `scipy`, `PyMC`.
- R only in CI, for `bayesPop` / `bayesTFR` / `bayesLife`.
- Site: Observable Framework (static), with Observable Plot / D3. Reports: Quarto → HTML + PDF (Typst).
- Hosting on GitHub Pages. DOIs via the Zenodo GitHub integration. Scheduled ingestion in GitHub Actions.
- No backend, no auth, no LLM features in the public product.

## Design system (PROPOSAL §7A)

- The chart title states the finding. The footer states source, dataset, vintage and `nature`.
- Epistemic grammar: solid = observed/estimate/derived; dashed + bands = projected; dotted in a different hue family = scenario; hollow marker = provisional; line gap + note = break in series.
- Greece gets the single accent colour, comparators are neutral, labels go directly on the lines.
- Choropleths show rates only and are paired with a cartogram or proportional symbols.
- Greek: no accented all-caps; locale number formatting via `Intl.NumberFormat` (`10.372.335`, `−0,03%`); true minus sign.
- Every chart has a data-table view, a CSV download and data-derived alt text. Target WCAG 2.2 AA.
- Playwright visual regression in light/dark/print. Inspect screenshots before every release.

## Working in `pipeline/` (Python package `grpop`)

Current state (Phase 0): `pipeline/` is the only code. The site, the Quarto reports and the DuckDB store listed under Stack are planned and don't exist yet.

- Before every push, run `cd pipeline && uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check .` and make sure it passes. CI (`.github/workflows/ci.yml`) runs the same steps with `uv sync --locked`. Ruff uses line length 100 and rule sets `E,F,I,B,UP,SIM,RUF`.
- To run a single test: `uv run pytest tests/test_provenance.py::test_duplicate_key_fails`.
- `src/grpop/provenance.py` is the provenance contract. Every published value must pass `validate_observations`. The schema is a pandera/polars `DataFrameModel` with these properties:
  - `strict=True`: undeclared columns are rejected.
  - `coerce=False`: types must already be correct, and `retrieved_at` must be a UTC-aware `Datetime`.
  - `definition_id` looks like `name@v1`. `period` is `YYYY`, `YYYY-MM` or `YYYY-MM-DD`.
  - Cross-field rules: `value` is null exactly when `status = not_available`, and `scenario_id` is set exactly when `nature = scenario`.
  - `OBSERVATION_KEY` must be unique. A second row with the same key is a revision and goes to a history table.
- `src/grpop/sources/jsonstat.py` turns Eurostat JSON-stat into long format: one string column per dimension, plus `value` and the source `flag` (e.g. `p` = provisional). Cells the source did not publish are kept as null rows, so "not published" stays distinct from "not requested".
- `src/grpop/sources/registry.yaml` lists every source, validated by `registry.py`, a pydantic model with `extra="forbid"`. The verification flow:
  1. The `Source probe` workflow runs `grpop-probe` weekly, on demand, and whenever `registry.yaml` or `probe.py` changes.
  2. It uploads `probe-report.md/json` as an artifact.
  3. The probe never edits the registry. A person or Claude reads the report and records it.
  4. Set an entry to `verified` only with `checked_at` and `evidence` (the run id and the observed result) taken from that report.
- Test fixtures that were hand-written rather than recorded from a real response must say so in a `_comment` field.

## Environment notes

- The cloud dev environment's network policy currently blocks the data-source hosts (Eurostat, ELSTAT, UN, World Bank, HMD, OpenAlex, GISCO, CRAN). Only package registries (PyPI, npm) are reachable. Use test fixtures locally and run real ingestion in GitHub Actions until the owner allows those domains.
- Cloud environment only: Chromium is preinstalled for Playwright (`/opt/pw-browsers`). Do not run `playwright install`.
- Windows: Windows has no IANA timezone database. Keep the `tzdata; sys_platform == 'win32'` dependency, because without it the UTC `retrieved_at` column panics in polars (`ZoneInfoNotFoundError: UTC`).
