# grpop: data pipeline

The Python package that fetches, validates and harmonizes the project's source data.

```bash
uv sync            # create the environment
uv run pytest      # run the tests
uv run ruff check  # lint
uv run grpop-probe --report probe-report.md   # check that every registered source is reachable (needs network access)
```

- `src/grpop/provenance.py`: the provenance contract. Every published value must pass `validate_observations`.
- `src/grpop/sources/registry.yaml`: the source registry. Each entry has a verification status that is only changed after reading a probe report.
- `src/grpop/sources/probe.py`: checks registry entries against the live sources. It runs in GitHub Actions, because the cloud dev environment cannot reach the data hosts.
