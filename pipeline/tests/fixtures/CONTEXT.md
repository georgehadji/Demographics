# pipeline/tests/fixtures/

Source responses recorded from the live APIs, named by dataset and the countries or regions kept. `jsonstat_sparse.json` is hand-written and says so.

| File | What it does |
|---|---|
| `elstat_spo18_t10_2025.xlsx` | ELSTAT SPO18 table 10: input of `test_elstat_xlsx.py` |
| `eurostat_demo_find_el.json` | Eurostat `demo_find`, Greece: connector and parser tests |
| `eurostat_demo_find_el_cy.json` | Eurostat `demo_find`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_frate_el_cy.json` | Eurostat `demo_frate`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_gind_el_cy.json` | Eurostat `demo_gind`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_minfind_el_cy.json` | Eurostat `demo_minfind`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_mlexpec_el_cy.json` | Eurostat `demo_mlexpec`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_pjan_el_cy.json` | Eurostat `demo_pjan`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_pjanbroad_el_cy.json` | Eurostat `demo_pjanbroad`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_pjanind_el_cy.json` | Eurostat `demo_pjanind`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_r_d2jan_el5.json` | Eurostat `demo_r_d2jan`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_find2_el5.json` | Eurostat `demo_r_find2`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_gind3_el5.json` | Eurostat `demo_r_gind3`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_minfind_el5.json` | Eurostat `demo_r_minfind`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_mlifexp_el5.json` | Eurostat `demo_r_mlifexp`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_pjanaggr3_el5.json` | Eurostat `demo_r_pjanaggr3`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_pjanaggr3_el_2025.json` | Eurostat `demo_r_pjanaggr3`, all Greek regions, 2025: hierarchy test in `test_harmonize.py` |
| `eurostat_demo_r_pjanind2_el5.json` | Eurostat `demo_r_pjanind2`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `gisco_nuts2_handwritten.geojson` | Hand-written GISCO-like GeoJSON (squares, not boundaries): `test_gisco.py`, `test_eurostat.py`, `test_build.py` |
| `eurostat_proj_25np_el_cy_pl.json` | Eurostat `proj_25np` (EUROPOP2025), Greece, Cyprus and Poland, 2025-2026, every projection type: input of `test_projections.py` |
| `un_wpp2024_ppp_poptot.xlsx` | UN WPP 2024 probabilistic total population (PPP/POPTOT), the published workbook (CC BY 3.0 IGO): input of `test_un_wpp.py` |
| `jsonstat_sparse.json` | Hand-written JSON-stat with unpublished cells: `test_jsonstat.py`, `test_probe.py` |
