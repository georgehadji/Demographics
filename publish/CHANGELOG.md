# Data releases

Each release of the data product, newest first. `grpop-publish` puts the entry of the version it publishes into the release (`CHANGELOG.md` in the zip) and refuses a version that is not the newest entry here. Versions follow semver: major for a changed definition or removed file, minor for new files or sources, patch for new data under the same definitions.

## 1.0.0 (to be released)

First release. Every file of the data product except the map geometry (GISCO terms are non-commercial; see `SOURCES.md` and LICENSE-CONTENT.md):

- Official Eurostat series for Greece, the EU and peers: population, natural change, net migration (an official estimate), mean age of mothers at first birth, life expectancy at 0 and 65, infant mortality; the same for Greek regions.
- Derived indicators checked against Eurostat's published values: dependency ratios, ageing index, population shares, median age, growth rate, total fertility rate; national and regional.
- EU-27 median of every national rate (`EU27_2020_MEDIAN`) and the peer groups (`peer_groups.json`).
- Projections: EUROPOP2025 (baseline and sensitivity tests as scenarios, ADR 0008) and UN WPP 2024 (median with 80% and 95% intervals).
- Five-year age groups of Greece and its NUTS 1-3 regions.
