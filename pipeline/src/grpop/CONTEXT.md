# pipeline/src/grpop/

The package, in layers (ADR 0005): sources and snapshots (L1), parse (L2), harmonize (L3), indicators (L4), build (L5).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `bibliography.py` | `grpop-bib`: resolves every DOI of `data/bibliography/references.csv` by content negotiation, checks title and authors, writes CSL-JSON with citation fields only |
| `publish.py` | `grpop-publish`: packages the data product as a reproducible zip (files whose sources allow commercial reuse, manifest, `SOURCES.md`, `snapshots.txt`, changelog entry) and deposits it on Zenodo |
| `build.py` | `grpop-build`: the data product. One step per indicator or series, validated, written as Parquet and CSV, listed in `manifest.json` with hashes; memoized; stops on unexplained differences from Eurostat. Also writes the map geometry (`GEOMETRY`) as GeoJSON with its licence, the peer groups as `peer_groups.json`, and adds the EU-27 median to national rates (`MEDIAN`). `PROJECTIONS`: EUROPOP2025 for Greece in detail and totals for every area, UN WPP 2024 for Greece and the peers |
| `definitions.py` | Typed, cached access to `definitions.yaml` (`get_definition`) |
| `definitions.yaml` | Every `definition_id`: meaning (in English, and in Greek under `el` for the site), metric, unit, version |
| `groups.py` | Peer groups (PROPOSAL §6) from `data/reference/peer_groups.csv`; the EU-27 median as `derived` rows (`EU27_2020_MEDIAN`); the build's check of members and of the very-low-fertility rule |
| `harmonize.py` | Greek NUTS codes: NUTS 2010 recodes, rejection of unknown codes, hierarchy check; `age_gaps`: age groups add up to the total |
| `indicators.py` | `INDICATORS` (derived, with official counterpart and corroboration) and `SERIES` (official, published as given); `compute`, `disagreements`, `check` |
| `parse` | Source bytes to long-format tables: see `parse/CONTEXT.md` |
| `decompose.py` | Δ9a: each year's change in Greek live births split, by mother's age, into the part from the number of women and the part from fertility (`demo_fagec`, `demo_pjan`), adding up exactly; provenance of two tables per ADR 0009 |
| `reconcile.py` | ELSTAT's natural movement against Eurostat (`demo_gind`, `demo_minfind`), run by each ELSTAT build step: every difference listed with its explanation, an unlisted or vanished one stops the build |
| `projections.py` | Official projections. EUROPOP2025 (`proj_25np`): baseline `projected`, sensitivity tests `scenario` (ADR 0008), base-year check against `demo_pjan`. UN WPP 2024: check of its medians against `demo_pjan` (`wpp_checked`) |
| `provenance.py` | The provenance contract: `Nature`, `Status`, `Sex`, age pattern, observation key, `validate_observations` |
| `snapshots.py` | Content-addressed store of raw downloads with an append-only `manifest.jsonl` |
| `sources` | Registry, connectors and probe: see `sources/CONTEXT.md` |
