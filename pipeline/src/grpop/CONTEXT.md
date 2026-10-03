# pipeline/src/grpop/

The package, in layers (ADR 0005): sources and snapshots (L1), parse (L2), harmonize (L3), indicators (L4), build (L5).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `build.py` | `grpop-build`: the data product. One step per indicator or series, validated, written as Parquet and CSV, listed in `manifest.json` with hashes; memoized; stops on unexplained differences from Eurostat. Also writes the map geometry (`GEOMETRY`) as GeoJSON with its licence, the peer groups as `peer_groups.json`, and adds the EU-27 median to national rates (`MEDIAN`). `PROJECTIONS`: EUROPOP2025 for Greece in detail and totals for every area |
| `definitions.py` | Typed, cached access to `definitions.yaml` (`get_definition`) |
| `definitions.yaml` | Every `definition_id`: meaning, metric, unit, version |
| `groups.py` | Peer groups (PROPOSAL §6) from `data/reference/peer_groups.csv`; the EU-27 median as `derived` rows (`EU27_2020_MEDIAN`); the build's check of members and of the very-low-fertility rule |
| `harmonize.py` | Greek NUTS codes: NUTS 2010 recodes, rejection of unknown codes, hierarchy check |
| `indicators.py` | `INDICATORS` (derived, with official counterpart and corroboration) and `SERIES` (official, published as given); `compute`, `disagreements`, `check` |
| `parse` | Source bytes to long-format tables: see `parse/CONTEXT.md` |
| `projections.py` | EUROPOP2025 national projections (`proj_25np`): baseline `projected`, sensitivity tests `scenario` (ADR 0008); base-year check against `demo_pjan` |
| `provenance.py` | The provenance contract: `Nature`, `Status`, `Sex`, age pattern, observation key, `validate_observations` |
| `snapshots.py` | Content-addressed store of raw downloads with an append-only `manifest.jsonl` |
| `sources` | Registry, connectors and probe: see `sources/CONTEXT.md` |
