import json
from pathlib import Path

import polars as pl
import pytest

from grpop.parse import jsonstat

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_sparse_dataset_expands_row_major():
    df = jsonstat.to_long(load("jsonstat_sparse.json"))
    assert df.columns == ["freq", "sex", "geo", "time", "value", "flag"]
    assert df.height == 1 * 2 * 2 * 2
    # Row-major order: the last dimension (time) varies fastest.
    assert df.select("sex", "geo", "time").rows()[:3] == [
        ("F", "EL", "2023"),
        ("F", "EL", "2024"),
        ("F", "IT", "2023"),
    ]


def test_missing_cells_are_null_and_keep_flags():
    df = jsonstat.to_long(load("jsonstat_sparse.json"))
    missing = df.filter(pl.col("sex") == "F", pl.col("geo") == "IT", pl.col("time") == "2024")
    assert missing["value"].to_list() == [None]
    assert missing["flag"].to_list() == [":"]
    provisional = df.filter(pl.col("sex") == "F", pl.col("geo") == "EL", pl.col("time") == "2024")
    assert provisional.select("value", "flag").row(0) == (11.0, "p")


def test_list_index_and_dense_values_match_sparse_form():
    doc = load("jsonstat_sparse.json")
    dense = dict(doc)
    dense["value"] = [doc["value"].get(str(i)) for i in range(8)]
    assert jsonstat.to_long(dense).equals(jsonstat.to_long(doc))


def test_size_mismatch_is_rejected():
    doc = load("jsonstat_sparse.json")
    doc["size"] = [1, 2, 2, 3]
    with pytest.raises(ValueError, match="size"):
        jsonstat.to_long(doc)


def test_non_dataset_is_rejected():
    with pytest.raises(ValueError, match="dataset"):
        jsonstat.to_long({"class": "collection"})


def test_summarize():
    summary = jsonstat.summarize(load("jsonstat_sparse.json"))
    assert summary["dimensions"] == {"freq": 1, "sex": 2, "geo": 2, "time": 2}
    assert summary["n_values"] == 7
