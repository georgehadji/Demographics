# .github/workflows/

Workflows (GitHub Actions). They run on GitHub because the cloud dev environment cannot reach the data hosts.

| File | What it does |
|---|---|
| `build.yml` | `Build`: restores the latest snapshots from the `snapshots` release, runs `grpop-build` twice from scratch and fails unless the outputs are identical. After each Ingest run, on demand, and on pushes that change code or reference data |
| `ci.yml` | `CI`: on every push and pull request. Pipeline job: `uv sync --locked`, ruff, ruff format, mypy, pytest. Design job: `npm ci`, `npm test`, `npm run build` |
| `ingest.yml` | `Ingest`: weekly and on demand, `grpop-ingest` downloads the Phase 1 Eurostat datasets and uploads new objects and a manifest part to the `snapshots` release. Nothing there is overwritten |
| `source-probe.yml` | `Source probe`: weekly, on demand and when the registry or probe code changes, `grpop-probe` checks every registry entry and uploads `probe-report.md/json` as an artifact |
