# pipeline/src/grpop/

The package, in layers (ADR 0005): sources and snapshots (L1), parse (L2), harmonize (L3), indicators (L4), build (L5).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `build.py` | `grpop-build`: the data product. One step per indicator or series, validated, written as Parquet and CSV, listed in `manifest.json` with hashes; memoized; stops on unexplained differences from Eurostat. Also writes the map geometry (`GEOMETRY`) as GeoJSON with its licence |
| `definitions.py` | Typed, cached access to `definitions.yaml` (`get_definition`) |
| `definitions.yaml` | Every `definition_id`: meaning, metric, unit, version |
| `harmonize.py` | Greek NUTS codes: NUTS 2010 recodes, rejection of unknown codes, hierarchy check |
| `indicators.py` | `INDICATORS` (derived, with official counterpart and corroboration) and `SERIES` (official, published as given); `compute`, `disagreements`, `check` |
| `parse` | Source bytes to long-format tables: see `parse/CONTEXT.md` |
| `provenance.py` | The provenance contract: `Nature`, `Status`, `Sex`, age pattern, observation key, `validate_observations` |
| `snapshots.py` | Content-addressed store of raw downloads with an append-only `manifest.jsonl` |
| `sources` | Registry, connectors and probe: see `sources/CONTEXT.md` |
