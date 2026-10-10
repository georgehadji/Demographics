"""Economic old-age dependency ratio (Δ9o), on recorded tables."""

import pytest
from test_indicators import data

from grpop import economic_dependency as e

# European Commission, 2024 Ageing Report (Institutional Paper 279), Table 3: Greece 2022
AGEING_REPORT_2022 = 56.2


def test_reproduces_the_ageing_report():
    df = e.economic_old_age_dependency(data(e.SOURCES))
    value = dict(df.select("period", "value").iter_rows())
    assert value["2022"] == pytest.approx(AGEING_REPORT_2022, abs=0.15)  # docstring
    assert set(df["dataset_code"]) == {"demo_pjanbroad+lfsa_pganws"}  # ADR 0009
    assert df.filter(df["period"] == "2021")["break_in_series"].item()  # LFS 2021
