# pipeline/src/grpop/parse/

Source bytes to long-format tables. Pure functions, no I/O (ADR 0005, L2).

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `elstat_xlsx.py` | Prototype reader for ELSTAT table SPO18/10 (population on 1 January) |
| `eurostat.py` | Eurostat JSON-stat snapshot to observations: the only place Eurostat codes and flags are translated |
| `jsonstat.py` | JSON-stat 2.0 to long format, keeping unpublished cells as null rows |
