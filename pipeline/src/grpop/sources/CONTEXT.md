# pipeline/src/grpop/sources/

Where data comes from (ADR 0005, L1).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `eurostat.py` | `grpop-ingest`: downloads whole Eurostat datasets into the snapshot store, with backoff |
| `probe.py` | `grpop-probe`: checks every registry entry against the live source and writes the probe report |
| `registry.py` | Typed, cached access to `registry.yaml` (`load_registry`, `get_source`), licence keys resolved |
| `registry.yaml` | Every source: provider, code, access, licence (by key), phase, verification with evidence |
