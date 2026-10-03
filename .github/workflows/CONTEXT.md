# .github/workflows/

Workflows (GitHub Actions). They run on GitHub because the cloud dev environment cannot reach the data hosts.

| File | What it does |
|---|---|
| `bibliography.yml` | `Bibliography`: weekly, on demand and when the reference list or its code changes, `grpop-bib` resolves every DOI, fails on one that does not resolve or match, and uploads `references.json` (CSL-JSON) as an artifact |
| `build.yml` | `Build`: restores the latest snapshots from the `snapshots` release, runs `grpop-build` twice from scratch and fails unless the outputs are identical, then renders `site/` from the product (uploaded as the `site` artifact) and checks that the wrong pages in `site/test/` fail. After each Ingest run, on demand, and on pushes that change code, reference data, the site, the charts or the tokens |
| `ci.yml` | `CI`: on every push and pull request. Pipeline job: `uv sync --locked`, ruff, ruff format, mypy, pytest. Design job: `npm ci`, `npm test`, `npm run build`. Charts job: `npm ci` in `design/` and `charts/`, `npm test`. Site job: `npm ci` in `design/`, `charts/` and `site/`, `npm test` in `site/` |
| `ingest.yml` | `Ingest`: weekly and on demand, `grpop-ingest` downloads the Phase 1-2 sources (Eurostat datasets and the files with `ingest` set) and uploads new objects and a manifest part to the `snapshots` release. Nothing there is overwritten |
| `publish.yml` | `Publish`: by hand only, with a version, a target (`sandbox` dry run or `zenodo`) and, for a later version, the Zenodo concept id. Builds the product twice, fails unless identical, packages it with `grpop-publish`, deposits it on Zenodo (secret `ZENODO_TOKEN` or `ZENODO_SANDBOX_TOKEN`) and, on zenodo.org, makes the GitHub Release `data-v<version>` |
| `source-probe.yml` | `Source probe`: weekly, on demand and when the registry or probe code changes, `grpop-probe` checks every registry entry and uploads `probe-report.md/json` as an artifact |
| `visual.yml` | `Visual`: on pushes and pull requests that touch `charts/`, `design/` or reference data, Playwright screenshots of every chart type in light, dark and print against the Linux baselines, and axe checks. Run by hand with `update` to rewrite the baselines and commit them |
