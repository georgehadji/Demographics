# pipeline/

The Python package `grpop` (uv project). Run from here: `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run mypy`.

| File | What it does |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, console scripts (`grpop-probe`, `grpop-ingest`, `grpop-build`), ruff, mypy and pytest settings |
| `README.md` | Short package README: commands and the main modules |
| `src` | Package code: see `src/grpop/CONTEXT.md` |
| `tests` | Tests: see `tests/CONTEXT.md` |
| `uv.lock` | Locked dependency versions (`uv sync --locked` in CI) |
