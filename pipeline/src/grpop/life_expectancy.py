"""The change in life expectancy at birth by age (Δ9i): Arriaga's decomposition, Greece.

The decomposition of Arriaga (1984), ``arriaga1984`` in data/bibliography. Between the
period life tables of the year before (1) and the year (2), the part of single age x is

    l1(x)/l1(0) * (L2(x)/l2(x) - L1(x)/l1(x))
      + T2(x+1)/l1(0) * (l1(x)/l2(x) - l1(x+1)/l2(x+1))

and of the open age class l1(x)/l1(0) * (T2(x)/l2(x) - T1(x)/l1(x)), from Eurostat
demo_mlifetable lx (SURVIVORS) and Tx (TOTPYLIVED). Lx is taken as T(x) - T(x+1), so
the parts add up exactly to T2(0)/l2(0) - T1(0)/l1(0), the change in life expectancy
(Eurostat's LIFEXP at 0 is the same to its one decimal; the build checks it). The
single ages are summed into the age groups of ``GROUPS``. Pairs of years whose open age
class differs, or with an age missing, are left out. By sex, Greece only.
"""

from __future__ import annotations

import polars as pl

from grpop.definitions import get_definition
from grpop.indicators import Data, Series
from grpop.provenance import AGE_TOTAL, Nature, Status, validate_observations

SOURCE = "eurostat_demo_mlifetable"
GEO = "EL"
SURVIVORS = Series(
    SOURCE,
    "life_table_survivors@v1",
    Nature.OFFICIAL_ESTIMATE,
    select={"indic_de": "SURVIVORS"},
    geo_prefix=GEO,
)
ABOVE = Series(
    SOURCE,
    "life_table_person_years_above@v1",
    Nature.OFFICIAL_ESTIMATE,
    select={"indic_de": "TOTPYLIVED"},
    geo_prefix=GEO,
)
LIFE_EXPECTANCY = Series(
    SOURCE,
    "life_expectancy@v1",
    Nature.OFFICIAL_ESTIMATE,
    select={"indic_de": "LIFEXP"},
    geo_prefix=GEO,
)
SOURCES = frozenset({SOURCE})
DEFINITION = "life_expectancy_change_by_age@v1"
TRANSFORM_VERSION = "arriaga_decomposition@0.1"
# Age groups of the parts: lower bound -> label (the last is open)
GROUPS = {0: "0", 1: "1-14", 15: "15-44", 45: "45-64", 65: "65-84", 85: "85+"}
# LIFEXP has one decimal: the change of two rounded values is within 0.1 of ours
TOLERANCE = 0.1 + 1e-9
_PROVENANCE = ["source", "dataset_code", "source_url", "vintage", "retrieved_at"]


def _table(data: Data) -> pl.DataFrame:
    """lx and Tx by sex, year and single age (x), with the open class flagged."""

    def read(series: Series, name: str) -> pl.DataFrame:
        df = series.read(data).filter(pl.col("value").is_not_null())
        return df.select(
            "sex",
            "period",
            "age",
            *_PROVENANCE,
            pl.col("value").alias(name),
            (pl.col("status") == Status.PROVISIONAL.value).alias(f"provisional_{name}"),
            pl.col("break_in_series").alias(f"break_{name}"),
        )

    lx, tx = read(SURVIVORS, "l"), read(ABOVE, "t")
    return (
        lx.join(tx.drop(_PROVENANCE), on=["sex", "period", "age"])
        .with_columns(
            x=pl.col("age").str.strip_suffix("+").cast(pl.Int32),
            open=pl.col("age").str.ends_with("+"),
            provisional=pl.col("provisional_l") | pl.col("provisional_t"),
            break_in_series=pl.col("break_l") | pl.col("break_t"),
        )
        .sort("sex", "period", "x")
    )


def _complete(table: pl.DataFrame) -> pl.DataFrame:
    """Years with every single age below the open class, and that class."""
    return (
        table.group_by("sex", "period")
        .agg(
            last=pl.col("x").filter(pl.col("open")).first(),
            n=pl.col("x").filter(~pl.col("open")).n_unique(),
            top=pl.col("x").filter(~pl.col("open")).max(),
        )
        .filter(
            pl.col("last").is_not_null(),
            pl.col("n") == pl.col("last"),
            pl.col("top") == pl.col("last") - 1,
        )
        .select("sex", "period", "last")
    )


def parts(data: Data) -> pl.DataFrame:
    """Part of each single age in the change from the year before: sex, period (the
    later year), x, part, provenance."""
    table = _table(data)
    years = _complete(table)
    table = table.join(years, on=["sex", "period"]).with_columns(
        l_next=pl.col("l").shift(-1).over("sex", "period"),
        t_next=pl.col("t").shift(-1).over("sex", "period"),
        l0=pl.col("l").first().over("sex", "period"),
    )
    before = table.select(
        "sex",
        period=(pl.col("period").cast(pl.Int32) + 1).cast(pl.String),
        x="x",
        last1="last",
        l1="l",
        t1="t",
        l1_next="l_next",
        t1_next="t_next",
        l1_0="l0",
        provisional1="provisional",
        break1="break_in_series",
        vintage1="vintage",
        retrieved1="retrieved_at",
    )
    both = table.join(before, on=["sex", "period", "x"]).filter(pl.col("last") == pl.col("last1"))
    lived1 = pl.col("t1") - pl.col("t1_next")
    lived2 = pl.col("t") - pl.col("t_next")
    closed = pl.col("l1") / pl.col("l1_0") * (lived2 / pl.col("l") - lived1 / pl.col("l1")) + (
        pl.col("t_next") / pl.col("l1_0")
    ) * (pl.col("l1") / pl.col("l") - pl.col("l1_next") / pl.col("l_next"))
    open_class = (
        pl.col("l1") / pl.col("l1_0") * (pl.col("t") / pl.col("l") - pl.col("t1") / pl.col("l1"))
    )
    return both.select(
        "sex",
        "period",
        "x",
        part=pl.when("open").then(open_class).otherwise(closed),
        e2=pl.col("t") / pl.col("l"),
        e1=pl.col("t1") / pl.col("l1"),
        provisional=pl.col("provisional") | pl.col("provisional1"),
        break_in_series=pl.col("break_in_series") | pl.col("break1"),
        source="source",
        dataset_code="dataset_code",
        source_url="source_url",
        vintage=pl.max_horizontal("vintage", "vintage1"),
        retrieved_at=pl.max_horizontal("retrieved_at", "retrieved1"),
    )


def _group(x: pl.Expr) -> pl.Expr:
    label = pl.lit(GROUPS[0])
    for lower, name in sorted(GROUPS.items()):
        label = pl.when(x >= lower).then(pl.lit(name)).otherwise(label)
    return label


def check_total(data: Data, changes: pl.DataFrame) -> None:
    """Our change equals the change of Eurostat's LIFEXP at 0 within its rounding."""
    e0 = LIFE_EXPECTANCY.read(data).filter(pl.col("age") == "0", pl.col("value").is_not_null())
    official = e0.join(
        e0.select(
            "sex", period=(pl.col("period").cast(pl.Int32) + 1).cast(pl.String), before="value"
        ),
        on=["sex", "period"],
    ).select("sex", "period", official=pl.col("value") - pl.col("before"))
    compared = changes.join(official, on=["sex", "period"])
    off = compared.filter((pl.col("change") - pl.col("official")).abs() > TOLERANCE)
    if not off.is_empty():
        raise ValueError(f"{DEFINITION}: change differs from LIFEXP: {off.head(5).rows()}")


def life_expectancy_change(data: Data) -> pl.DataFrame:
    """The parts by age group and the whole change, by sex, as observations."""
    single = parts(data).with_columns(age=_group(pl.col("x"))).sort("sex", "period", "x")
    keys = ["sex", "period"]
    provenance = [
        pl.col("provisional").any(),
        pl.col("break_in_series").any(),
        *(pl.col(c).first() for c in ["source", "dataset_code", "source_url"]),
        pl.col("vintage").max(),
        pl.col("retrieved_at").max(),
    ]
    grouped = single.group_by(*keys, "age", maintain_order=True).agg(
        *provenance, value=pl.col("part").sum()
    )
    total = single.group_by(*keys, maintain_order=True).agg(
        *provenance,
        value=pl.col("part").sum(),
        change=pl.col("e2").first() - pl.col("e1").first(),
    )
    off = total.filter((pl.col("value") - pl.col("change")).abs() > 1e-9)
    if not off.is_empty():
        raise ValueError(f"{DEFINITION}: parts do not add up: {off.head(5).rows()}")
    check_total(data, total)
    definition = get_definition(DEFINITION)
    rows = pl.concat(
        [grouped, total.drop("change").with_columns(age=pl.lit(AGE_TOTAL))], how="diagonal"
    )
    return validate_observations(
        rows.select(
            metric=pl.lit(definition.metric),
            definition_id=pl.lit(DEFINITION),
            geo_code=pl.lit(GEO),
            geo_vintage=pl.lit("NUTS2024"),
            period="period",
            sex="sex",
            age="age",
            value="value",
            unit=pl.lit(definition.unit),
            source="source",
            dataset_code="dataset_code",
            source_url="source_url",
            vintage="vintage",
            retrieved_at="retrieved_at",
            transform_version=pl.lit(TRANSFORM_VERSION),
            nature=pl.lit(Nature.DERIVED.value),
            status=pl.when("provisional")
            .then(pl.lit(Status.PROVISIONAL.value))
            .otherwise(pl.lit(Status.FINAL.value)),
            break_in_series="break_in_series",
            scenario_id=pl.lit(None, dtype=pl.String),
            interval=pl.lit(None, dtype=pl.String),
        ).sort("period", "sex", "age")
    )
