# pipeline/tests/

pytest suite. Fixtures are recorded from real responses; hand-written ones say so in `_comment`.

| File | What it does |
|---|---|
| `fixtures` | Recorded source responses: see `fixtures/CONTEXT.md` |
| `test_build.py` | Two builds give the same bytes; manifest complete; only changed outputs rebuilt; unexplained or stale differences stop the build |
| `test_context.py` | Every tracked file is listed in its folder's `CONTEXT.md`, every listed file exists, and the root map links every folder map |
| `test_definitions.py` | `definitions.yaml` loads; duplicate or malformed ids are rejected |
| `test_docs.py` | README lists every source host; Eurostat codes named in live docs exist in the registry |
| `test_elstat_xlsx.py` | The ELSTAT SPO18/10 reader on a recorded table |
| `test_eurostat.py` | The Eurostat connector: whole-dataset URL, retries on network errors and 5xx, one snapshot per response |
| `test_eurostat_parse.py` | Eurostat flags, sex and age codes, select guard, on recorded responses |
| `test_gisco.py` | The Greek map geometry: regions kept and sorted, licence and attribution, rounding, a missing region fails |
| `test_groups.py` | Peer groups: versions, the EU-27 median against `statistics.median`, its completeness and status, the members and rule check; hand-written rows |
| `test_harmonize.py` | NUTS recodes, unknown codes, hierarchy sums on real regional data |
| `test_indicators.py` | Acceptance tests generated from `INDICATORS` and `SERIES`: contract and agreement with Eurostat; `RECORDED` maps sources to fixtures |
| `test_jsonstat.py` | JSON-stat to long format, including unpublished cells |
| `test_probe.py` | The probe: JSON-stat check on a fixture, HTTP and network errors reported, report escaping |
| `test_projections.py` | EUROPOP2025: baseline and scenarios, Greece's base year equals `demo_pjan`, unexplained or vanished base-year differences, unknown projection types |
| `test_un_wpp.py` | UN WPP 2024: Greece's median and ordered bounds, ISO2 mapping, years, the check against `demo_pjan` |
| `test_provenance.py` | Every rule of the provenance contract |
| `test_registry.py` | Registry validation: licence keys and terms, verification evidence, duplicate ids, unknown fields |
| `test_snapshots.py` | Content addressing, no overwrite, revisions as history, corrupt objects detected |
