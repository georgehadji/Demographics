from datetime import UTC, datetime

import pandera.errors
import polars as pl
import pytest

from grpop.provenance import Nature, Sex, Status, validate_observations

# Illustrative row. The value is a placeholder, not a real statistic: tests check the
# contract, not demographic facts.
BASE_ROW = {
    "metric": "population_1jan",
    "definition_id": "pop_usual_residence_1jan@v1",
    "geo_code": "EL",
    "geo_vintage": "NUTS2024",
    "period": "2025-01-01",
    "sex": Sex.TOTAL.value,
    "age": "total",
    "value": 1.0,
    "unit": "persons",
    "source": "Eurostat",
    "dataset_code": "demo_pjan",
    "source_url": "https://example.org/placeholder",
    "vintage": "placeholder-vintage",
    "retrieved_at": datetime(2026, 1, 1, tzinfo=UTC),
    "transform_version": "0.0.1",
    "nature": Nature.OFFICIAL_ESTIMATE.value,
    "status": Status.FINAL.value,
    "scenario_id": None,
}

SCHEMA = {
    "metric": pl.String,
    "definition_id": pl.String,
    "geo_code": pl.String,
    "geo_vintage": pl.String,
    "period": pl.String,
    "sex": pl.String,
    "age": pl.String,
    "value": pl.Float64,
    "unit": pl.String,
    "source": pl.String,
    "dataset_code": pl.String,
    "source_url": pl.String,
    "vintage": pl.String,
    "retrieved_at": pl.Datetime(time_zone="UTC"),
    "transform_version": pl.String,
    "nature": pl.String,
    "status": pl.String,
    "scenario_id": pl.String,
}


def frame(*rows: dict) -> pl.DataFrame:
    return pl.DataFrame([{**BASE_ROW, **r} for r in rows], schema=SCHEMA)


def test_valid_row_passes():
    validate_observations(frame({}))


@pytest.mark.parametrize(
    "override",
    [
        {"source_url": "http://insecure.example.org"},
        {"nature": "verified"},  # the v1 label that conflated "official" with "verified"
        {"status": "unknown"},
        {"definition_id": "no_version"},
        {"period": "Jan 2025"},
        {"unit": ""},
    ],
)
def test_invalid_field_fails(override):
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame(override))


def test_missing_provenance_column_fails():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({}).drop("vintage"))


def test_undeclared_column_fails():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({}).with_columns(pl.lit("x").alias("comment")))


def test_naive_timestamp_fails():
    df = frame({}).with_columns(pl.col("retrieved_at").dt.replace_time_zone(None))
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(df)


def test_null_value_requires_not_available():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"value": None}))
    validate_observations(frame({"value": None, "status": Status.NOT_AVAILABLE.value}))


def test_not_available_must_have_null_value():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"status": Status.NOT_AVAILABLE.value}))


def test_scenario_requires_scenario_id():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"nature": Nature.SCENARIO.value}))
    validate_observations(frame({"nature": Nature.SCENARIO.value, "scenario_id": "tfr_1_5"}))


def test_scenario_id_forbidden_outside_scenarios():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"scenario_id": "tfr_1_5"}))


def test_duplicate_key_fails():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({}, {"value": 2.0}))


def test_same_period_from_two_sources_is_allowed():
    validate_observations(frame({}, {"source": "ELSTAT", "dataset_code": "elstat_pop_est"}))


@pytest.mark.parametrize("age", ["total", "unknown", "0", "100", "15-64", "85+"])
def test_valid_ages_pass(age):
    validate_observations(frame({"age": age}))


@pytest.mark.parametrize("age", ["", "Y15", "Y_GE85", "15-", "64-15", "15-15", "-5", "1000"])
def test_invalid_ages_fail(age):
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"age": age}))


def test_sex_outside_vocabulary_fails():
    with pytest.raises(pandera.errors.SchemaErrors):
        validate_observations(frame({"sex": "T"}))


def test_sex_and_age_are_part_of_the_key():
    validate_observations(
        frame({}, {"sex": Sex.MALE.value}, {"sex": Sex.FEMALE.value}, {"age": "0"})
    )
