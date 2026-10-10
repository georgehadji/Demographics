# pipeline/tests/fixtures/

Source responses recorded from the live APIs, named by dataset and the countries or regions kept. `jsonstat_sparse.json` is hand-written and says so.

| File | What it does |
|---|---|
| `csl_kohler2002.json` | CSL-JSON of DOI 10.1111/j.1728-4457.2002.00641.x from doi.org, trimmed by hand (abstract and unread fields removed; see its `_comment`): input of `test_bibliography.py` |
| `elstat_spo03_2025.pdf` | ELSTAT press release "Φυσική Κίνηση Πληθυσμού 2025" (1 October 2026), unmodified, sha256 `7d465036…`: input of `test_elstat_pdf.py` |
| `elstat_spo18_t10_2025.xlsx` | ELSTAT SPO18 table 10: input of `test_elstat_xlsx.py` |
| `eurostat_demo_fagec_el_cy.json` | Eurostat `demo_fagec` (births by mother's age), Greece and Cyprus, 2022 onwards: input of `test_decompose.py` |
| `eurostat_demo_fasec_el_cy.json` | Eurostat `demo_fasec`, Greece and Cyprus, births at every age of the mother by newborn's sex, 2021 onwards: input of `test_reproduction.py` |
| `eurostat_demo_fmonth_el_cy.json` | Eurostat `demo_fmonth`, Greece and Cyprus, births by month, 1960-2025 (2025 January-September, provisional): input of `test_nowcast.py` |
| `eurostat_demo_fordagec_el_cy.json` | Eurostat `demo_fordagec` (births by mother's age and birth order), Greece and Cyprus, 2021 onwards: input of `test_birth_order.py` |
| `eurostat_demo_find_el.json` | Eurostat `demo_find`, Greece: connector and parser tests |
| `eurostat_demo_find_el_cy.json` | Eurostat `demo_find`, Greece and Cyprus, 2021 onwards: total fertility rate, mean ages at birth (all orders and by order) and share of births outside marriage; input of `test_indicators.py` and `test_birth_order.py` |
| `eurostat_demo_frate_el_cy.json` | Eurostat `demo_frate`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_gind_el_cy.json` | Eurostat `demo_gind`, Greece and Cyprus, 2021 onwards: input of `test_indicators.py` and of the reconciliation in `test_elstat_pdf.py` |
| `eurostat_demo_minfind_el_cy.json` | Eurostat `demo_minfind` (infant and neonatal mortality), Greece and Cyprus, 2021 onwards: input of `test_indicators.py` and of the reconciliation in `test_elstat_pdf.py` |
| `eurostat_demo_mlexpec_el_cy.json` | Eurostat `demo_mlexpec`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_mlifetable_el_cy.json` | Eurostat `demo_mlifetable`, Greece and Cyprus, death rate, probability of dying, life expectancy, survivors and person-years above each age, 2022 onwards: input of `test_indicators.py`, `test_prospective.py`, `test_reproduction.py` and `test_life_expectancy.py` |
| `eurostat_demo_mexrt_el.json` | Eurostat `demo_mexrt`, Greece, excess mortality by month, 2020-01 to 2026-06: official counterpart in `test_indicators.py` |
| `eurostat_demo_mager_el.json` | Eurostat `demo_mager` (deaths by age reached), Greece, 2023-2024: input of `test_migration.py` |
| `eurostat_migr_imm8_el.json` | Eurostat `migr_imm8` (immigration by age), Greece, 2023-2024: input of `test_indicators.py` and `test_migration.py` |
| `eurostat_migr_emi2_el.json` | Eurostat `migr_emi2` (emigration by age), Greece, 2023-2024: input of `test_indicators.py` and `test_migration.py` |
| `eurostat_hlth_cd_apr_el_cy.json` | Eurostat `hlth_cd_apr` (avoidable, preventable and treatable mortality, all causes), Greece and Cyprus, 2021-2023: input of `test_indicators.py` |
| `eurostat_demo_nind_el_cy.json` | Eurostat `demo_nind` (marriage indicators), Greece and Cyprus, 2021 onwards: input of `test_indicators.py` and of the reconciliation in `test_elstat_pdf.py` |
| `eurostat_demo_ndivind_el_cy.json` | Eurostat `demo_ndivind` (divorce indicators), Greece and Cyprus, 2021 onwards: input of `test_indicators.py` and of the reconciliation in `test_elstat_pdf.py` |
| `eurostat_demo_pjan_el_cy.json` | Eurostat `demo_pjan`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_pjan_totals_el_cy.json` | Eurostat `demo_pjan`, Greece and Cyprus, totals, 2019 onwards: input of `test_projection_accuracy.py` (the base years) |
| `eurostat_demo_pjanbroad_el_cy.json` | Eurostat `demo_pjanbroad`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_pjanind_el_cy.json` | Eurostat `demo_pjanind`, Greece and Cyprus: input of `test_indicators.py` |
| `eurostat_demo_r_d2jan_el5.json` | Eurostat `demo_r_d2jan`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_mwk_ts_el.json` | Eurostat `demo_r_mwk_ts`, Greece, total deaths by week, 2015-W53 to 2026-W27: input of `test_indicators.py` and `test_excess_mortality.py` |
| `eurostat_demo_r_find2_el5.json` | Eurostat `demo_r_find2`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_gind3_el5.json` | Eurostat `demo_r_gind3`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_minfind_el5.json` | Eurostat `demo_r_minfind`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_mlifexp_el5.json` | Eurostat `demo_r_mlifexp`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_pjanaggr3_el5.json` | Eurostat `demo_r_pjanaggr3`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_demo_r_pjanaggr3_el_2025.json` | Eurostat `demo_r_pjanaggr3`, all Greek regions, 2025: hierarchy test in `test_harmonize.py` |
| `eurostat_demo_r_pjanind2_el5.json` | Eurostat `demo_r_pjanind2`, EL, EL5 and some of its regions: input of `test_indicators.py` |
| `eurostat_yth_demo_030_el_cy.json` | Eurostat `yth_demo_030` (age of leaving the parental household), Greece and Cyprus, 2021 onwards: input of `test_indicators.py` |
| `gisco_nuts2_handwritten.geojson` | Hand-written GISCO-like GeoJSON (squares, not boundaries; GISCO's Greek names): `test_gisco.py`, `test_eurostat.py`, `test_build.py` |
| `eurostat_proj_25np_el_cy_pl.json` | Eurostat `proj_25np` (EUROPOP2025), Greece, Cyprus and Poland, 2025-2026, every projection type: input of `test_projections.py` |
| `eurostat_proj_19np_el_cy.json` | Eurostat `proj_19np` (EUROPOP2019), Greece and Cyprus, totals, 2019-2026, every projection type: input of `test_projection_accuracy.py` |
| `eurostat_proj_23np_el_cy.json` | Eurostat `proj_23np` (EUROPOP2023), Greece and Cyprus, totals, 2022-2026, every projection type: input of `test_projection_accuracy.py` |
| `un_wpp2024_ppp_poptot.xlsx` | UN WPP 2024 probabilistic total population (PPP/POPTOT), the published workbook (CC BY 3.0 IGO): input of `test_un_wpp.py` |
| `eurostat_demo_r_pjangrp3_el5.json` | Eurostat `demo_r_pjangrp3`, EL, EL5, EL51-EL54 and EL511, 2023 onwards: input of `test_indicators.py` and `test_harmonize.py` |
| `jsonstat_sparse.json` | Hand-written JSON-stat with unpublished cells: `test_jsonstat.py`, `test_probe.py` |
