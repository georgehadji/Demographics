"""Peer groups and the EU-27 median, on hand-written rows."""

import statistics
from datetime import UTC, datetime

import polars as pl
import pytest

from grpop import build, groups
from grpop.provenance import validate_observations

EU = groups.members("eu27")


def rows(values: dict[str, float | None], period: str = "2024", **extra: object) -> pl.DataFrame:
    n = len(values)
    return validate_observations(
        pl.DataFrame(
            {
                "metric": ["total_fertility_rate"] * n,
                "definition_id": ["total_fertility_rate@v1"] * n,
                "geo_code": list(values),
                "geo_vintage": ["NUTS2024"] * n,
                "period": [period] * n,
                "sex": ["total"] * n,
                "age": ["total"] * n,
                "value": list(values.values()),
                "unit": ["live births per woman"] * n,
                "source": ["Eurostat"] * n,
                "dataset_code": ["demo_find"] * n,
                "source_url": ["https://example.org/x"] * n,
                "vintage": ["2026-09-25"] * n,
                "retrieved_at": [datetime(2026, 9, 29, tzinfo=UTC)] * n,
                "transform_version": ["eurostat@0.1"] * n,
                "nature": ["official_estimate"] * n,
                "status": ["not_available" if v is None else "final" for v in values.values()],
                "break_in_series": [False] * n,
                "scenario_id": pl.Series([None] * n, dtype=pl.String),
                "interval": pl.Series([None] * n, dtype=pl.String),
            }
        ).with_columns(**{k: pl.lit(v) for k, v in extra.items()})
    )


def test_groups_are_versioned_and_known():
    assert set(groups.GROUPS["group"]) == {
        "eu27",
        "southern_europe",
        "south_east_europe",
        "very_low_fertility",
    }
    assert len(EU) == len(set(EU)) == 27
    assert set(groups.members("very_low_fertility")) <= set(EU)
    assert groups.GROUPS.group_by("group").agg(pl.col("version").n_unique())["version"].max() == 1
    with pytest.raises(ValueError, match="unknown peer group"):
        groups.members("nordic")


def test_median_is_the_median_of_the_27_values():
    values = {g: 1.0 + i / 10 for i, g in enumerate(EU)}
    out = groups.median(rows({**values, "EU27_2020": 1.4, "NO": 9.0}))
    assert out["geo_code"].to_list() == [groups.MEDIAN_GEO]
    assert out["value"][0] == statistics.median(values.values())
    assert out["nature"][0] == "derived"
    validate_observations(groups.with_median(rows(values)))


def test_median_needs_every_member_and_inherits_status():
    values = {g: 1.5 for g in EU}
    assert groups.median(rows({**values, EU[0]: None})).height == 0
    provisional = rows(values).with_columns(
        status=pl.when(pl.col("geo_code") == EU[0]).then(pl.lit("provisional")).otherwise("status")
    )
    assert groups.median(provisional)["status"][0] == "provisional"


def test_median_refuses_mixed_definitions():
    df = pl.concat(
        [
            rows({g: 1.5 for g in EU}),
            rows({"EL": 1.0}).with_columns(definition_id=pl.lit("other@v1")),
        ]
    )
    with pytest.raises(ValueError, match="mixes definitions"):
        groups.median(df)


def test_check_finds_missing_members_and_a_broken_rule():
    vlf = set(groups.members("very_low_fertility"))
    tfr = rows({g: 1.2 if g in vlf else 1.5 for g in EU})
    population = rows({g: 1.0 for g in groups.GROUPS["geo_code"].unique()})
    assert set(groups.check(population, tfr)["groups"]) == set(groups.GROUPS["group"])
    with pytest.raises(ValueError, match="without a population value"):
        groups.check(population.filter(pl.col("geo_code") != "MT"), tfr)
    with pytest.raises(ValueError, match="the rule now gives"):
        groups.check(population, tfr.with_columns(value=pl.lit(1.2)))
    with pytest.raises(ValueError, match="incomplete"):
        groups.check(population, tfr.filter(pl.col("geo_code") != "MT"))


def test_the_median_is_added_to_national_rates_only():
    assert {"total_fertility_rate", "life_expectancy_0", "median_age"} <= build.MEDIAN
    assert not {"population", "net_migration", "total_fertility_rate_regional"} & build.MEDIAN


def test_median_keeps_vintages_apart_and_skips_bounds():
    values = {g: 1.5 for g in EU}
    two = pl.concat([rows(values), rows(values).with_columns(vintage=pl.lit("2025-01-01"))])
    assert sorted(groups.median(two)["vintage"]) == ["2025-01-01", "2026-09-25"]
    bounds = rows(values).with_columns(interval=pl.lit("80_lower"))
    assert groups.median(bounds).height == 0
    assert (
        groups.median(rows(values).with_columns(status=pl.lit("revised")))["status"][0] == "final"
    )
