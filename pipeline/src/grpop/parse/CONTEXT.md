# pipeline/src/grpop/parse/

Source bytes to long-format tables. Pure functions, no I/O (ADR 0005, L2).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `elstat_xlsx.py` | Prototype reader for ELSTAT table SPO18/10 (population on 1 January) |
| `eurostat.py` | Eurostat JSON-stat snapshot to observations: the only place Eurostat codes and flags are translated |
| `gisco.py` | GISCO NUTS GeoJSON snapshot to the Greek regions of one level, checked against `data/reference/nuts2024_el.csv`, with provenance and licence (attribution) inside; each region's Greek name from GISCO, Latin look-alike capitals written in Greek |
| `un_wpp.py` | UN WPP 2024 probabilistic total population workbook to observations: median plus 80/95% bounds as `interval` rows, ISO2 codes mapped by `data/reference/iso2_eurostat.csv` |
| `jsonstat.py` | JSON-stat 2.0 to long format, keeping unpublished cells as null rows |
