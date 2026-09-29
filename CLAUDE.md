# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Κοόρτες / Kohortes** (open demographic analysis of Greece; see ADR 0003): a non-commercial research and publication project on the demography of Greece. Goal: public credibility.
Claude builds everything (code, analysis, text, design). The responsible editor is **Georgios-Chrysovalantis Chatzivantsidis**, who approves every publication.
There is **no external reviewer yet**. Publications must carry their review tier (PROPOSAL §1B) and must never be presented as reviewed. See `AI_USE.md`.
Licences: code MIT, content and derived data CC BY 4.0, subject to the source terms.
The authoritative plan is `docs/PROPOSAL.md` (Greek). Decisions live in `docs/decisions/`. Read both before starting a new phase.

## Non-negotiable rules

- **Single source of truth ([ADR 0006](docs/decisions/0006-single-source-of-truth.md)).** Every fact has exactly one home (the table in ADR 0006). Code reads it and text links to it; never copy values (codes, URLs, numbers, licence terms, units, colours) into a second place. Derived files are generated, never hand-edited. When you find a duplicate, remove it or add it to step A5 of `docs/IMPLEMENTATION-PLAN.md`.
- **No number without provenance.** Every value passes the contract in `pipeline/src/grpop/provenance.py`, which defines the fields, the `nature`/`status` vocabulary and the observation key. `retrieved_at` is set by the pipeline, never by hand. Official ≠ verified: ELSTAT net migration is an `official_estimate`.
- **Never type a number into prose.** Publications are Quarto documents with inline computed values.
- **Never write a citation from memory.** Every DOI is resolved and matched against title and authors before use.
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
- Epistemic grammar: solid = observed/estimate/derived; dashed + bands = projected; dotted in a different hue family = scenario; hollow marker = provisional; line gap + note = break in series.
- Greece gets the single accent colour, comparators are neutral, labels go directly on the lines.
- Choropleths show rates only and are paired with a cartogram or proportional symbols.
- Greek: no accented all-caps; locale number formatting via `Intl.NumberFormat` (`10.372.335`, `−0,03%`); true minus sign.
- Every chart has a data-table view, a CSV download and data-derived alt text. Target WCAG 2.2 AA.
- Playwright visual regression in light/dark/print. Inspect screenshots before every release.

## Working in `pipeline/` (Python package `grpop`)

Current state: Phase 0 is closing (see `docs/IMPLEMENTATION-PLAN.md`); `pipeline/` is the only code. The site, the reports and the snapshot store are planned (ADR 0005) and don't exist yet.

- Before every push, run `cd pipeline && uv sync && uv run pytest -q && uv run ruff check . && uv run ruff format --check .` and make sure it passes. CI (`.github/workflows/ci.yml`) runs the same steps with `uv sync --locked`; lint settings are in `pyproject.toml`.
- To run a single test: `uv run pytest tests/test_provenance.py::test_duplicate_key_fails`.
- `src/grpop/provenance.py` is the provenance contract. Every published value must pass `validate_observations`. The schema is strict and never coerces types: read the module before producing observations. Breakdowns by sex and age are the `sex` and `age` columns, never separate metrics; totals are explicit values, not null.
- `src/grpop/definitions.yaml` defines every `definition_id` (meaning, unit, version). Parsers and indicators read metric and unit from it via `get_definition`; they never type them.
- Parsers take source metadata from the registry via `get_source(<id>)`, not from constants. Example: `src/grpop/sources/elstat_xlsx.py`.
- `src/grpop/sources/jsonstat.py` turns Eurostat JSON-stat into long format: one string column per dimension, plus `value` and the source `flag` (e.g. `p` = provisional). Cells the source did not publish are kept as null rows, so "not published" stays distinct from "not requested".
- `src/grpop/sources/registry.yaml` lists every source, validated by `registry.py`. Each licence is written once under `licences` and referenced by key from each source; an unknown or unused key is an error. The verification flow:
  1. The `Source probe` workflow runs `grpop-probe` weekly, on demand, and whenever `registry.yaml` or `probe.py` changes.
  2. It uploads `probe-report.md/json` as an artifact.
  3. The probe never edits the registry. A person or Claude reads the report and records it.
  4. Set an entry to `verified` only with `checked_at` and `evidence` (the run id and the observed result) taken from that report.
- Test fixtures that were hand-written rather than recorded from a real response must say so in a `_comment` field.

## Environment notes

- The cloud dev environment's network policy currently blocks the data-source hosts (the list in `README.md`, checked against the registry by `tests/test_docs.py`). Only package registries (PyPI, npm) are reachable. Use test fixtures locally and run real ingestion in GitHub Actions until the owner allows those domains.
- Cloud environment only: Chromium is preinstalled for Playwright (`/opt/pw-browsers`). Do not run `playwright install`.
- Windows: Windows has no IANA timezone database. Keep the `tzdata; sys_platform == 'win32'` dependency, because without it the UTC `retrieved_at` column panics in polars (`ZoneInfoNotFoundError: UTC`).
