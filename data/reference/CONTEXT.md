# data/reference/

Small, versioned reference tables read by the pipeline and the charts (ADR 0006: geographic correspondences live here).

| File | What it does |
|---|---|
| `el_nuts2_tiles.csv` | Grid position (row, column) of each Greek NUTS 2 region in tile-grid small multiples, read by `charts/src/tiles.js` callers |
| `elstat_regions_nuts.csv` | ELSTAT region labels (normalised English) to NUTS code and vintage, read by `parse/elstat_xlsx.py` |
| `peer_groups.csv` | Members and version of each peer group (group, version, geo_code), read by `pipeline/src/grpop/groups.py`, which documents each group's basis |
| `iso2_eurostat.csv` | ISO 3166-1 alpha-2 codes that Eurostat writes differently (GR → EL, GB → UK), read by `parse/un_wpp.py` |
| `nuts2010_el_recodes.csv` | Greek NUTS 2 codes that changed between NUTS 2010 and 2013 (code change only), read by `harmonize.recode_nuts2010` |
| `nuts2024_el.csv` | The Greek NUTS 2024 codes (from GISCO), the reference list `harmonize.check_greek_codes` checks against |
