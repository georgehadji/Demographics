# CLAUDE.md

Non-commercial research and publication project on the demography of Greece. Goal: public credibility.
Claude builds everything (code, analysis, text, design). A named human owner approves publications, and external experts review them.
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

## Environment notes

- The cloud dev environment's network policy currently blocks the data-source hosts (Eurostat, ELSTAT, UN, World Bank, HMD, OpenAlex, GISCO, CRAN). Only package registries (PyPI, npm) are reachable. Use test fixtures locally and run real ingestion in GitHub Actions until the owner allows those domains.
- Chromium is preinstalled for Playwright (`/opt/pw-browsers`). Do not run `playwright install`.
