"""ELSTAT natural movement of population, the yearly press release (SPO03) -> observations.

Reads Tables 1-10 and 12, and Table 11 as a check, never the % columns or the prose:

1. births, deaths and natural change of Greece, 1932 onwards with gaps;
2. births and deaths of the latest year by place of usual residence: regions and
   regional units (data/reference/elstat_areas_el.csv);
3. births by the mother's age group, every tenth year;
4. births by sex, by the mother's citizenship, inside or outside marriage or
   registered partnership, the last five years;
6. deaths by sex and age group, the last two years;
5. births by delivery method (normal or caesarean), the last five years;
7. stillbirths, infant deaths and the infant, perinatal and neonatal mortality rates,
   2015 onwards, with the break its footnote names;
8. marriages, civil marriages and civil partnerships, selected years from 1932 ("-",
   before civil marriage or partnerships existed, is not published);
9. spouses at their first marriage by sex and age group, the latest year;
10. divorces and divorces per 100 marriages, the last five years;
11. divorces by type and by duration of the marriage, the last two years: read for
    their totals only, as the contract has no dimension for type or duration;
12. divorced persons by sex and age group, the latest year.

Each table is located by its title and each row by its year or its label. The release
is checked against itself, and anything that does not add up raises: births minus
deaths equal natural change; every table's totals equal Table 1; the regions plus
"Εξωτερικό" (residence abroad, read for this check only) add up to the country and each
region's units to the region (Attica is given as a whole); age groups, sexes,
citizenships, marital status and delivery methods add up to their total; the infant
mortality rate is infant deaths per 1,000 live births; religious and civil marriages add
up to marriages, and marriages and partnerships to their sum; divorces per 100 marriages
follow from Tables 8 and 10; Table 11's types and durations add up to Table 10's
divorces, and the divorced men and women of Table 12 to two per divorce (a divorce of
two men or two women counts two of one sex); the printed shares of births outside
marriage (Table 4) and of normal and caesarean births (Graph 3) follow from the counts,
rounded half up. A value printed in two tables is published once.
Regional units that NUTS 2024 merges into one NUTS 3 region are summed into a
``derived`` value; deaths per 100 live births (the country every year, the regions the
latest year) are ``derived`` too; ELSTAT's rates are ``official_estimate``. Greek mothers and births
inside marriage are the total minus the published counts, so they are not published;
so are religious marriages. Births whose delivery method was not declared are the total
minus normal and caesarean births.
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence

import pdfplumber
import polars as pl

from grpop.definitions import get_definition
from grpop.harmonize import REFERENCE
from grpop.provenance import AGE_TOTAL, Nature, Sex, Status
from grpop.snapshots import Snapshot
from grpop.sources.registry import get_source

SOURCE_ID = "elstat_spo03_2025"
TRANSFORM_VERSION = "elstat_spo03_pdf@0.1"
BIRTHS, DEATHS, NATURAL_CHANGE = "live_births@v1", "deaths@v1", "natural_change@v1"
DEATHS_PER_BIRTHS = "deaths_per_100_live_births@v1"
FOREIGN_MOTHER = "live_births_foreign_citizen_mother@v1"
OUTSIDE_MARRIAGE = "live_births_outside_marriage@v1"
OUTSIDE_SHARE = "live_births_outside_marriage_share@v1"
STILLBIRTHS = "stillbirths@v1"
INFANT_RATE = "infant_mortality_rate@v1"
PERINATAL_RATE = "perinatal_mortality_rate@v1"
NEONATAL_RATE = "neonatal_mortality_rate@v1"
NORMAL_DELIVERY = "live_births_normal_delivery@v1"
CAESAREAN = "live_births_caesarean@v1"
CAESAREAN_SHARE = "caesarean_share@v1"
MARRIAGES = "marriages@v1"
CIVIL_MARRIAGES = "civil_marriages@v1"
PARTNERSHIPS = "civil_partnerships@v1"
FIRST_MARRIAGES = "first_marriages@v1"
DIVORCES = "divorces@v1"
DIVORCE_RATIO = "divorces_per_100_marriages@v1"
DIVORCED = "divorced_persons@v1"
DEFINITIONS = (
    BIRTHS, DEATHS, NATURAL_CHANGE, FOREIGN_MOTHER, OUTSIDE_MARRIAGE,
    STILLBIRTHS, INFANT_RATE, PERINATAL_RATE, NEONATAL_RATE,
    NORMAL_DELIVERY, CAESAREAN, MARRIAGES, CIVIL_MARRIAGES, PARTNERSHIPS,
    FIRST_MARRIAGES, DIVORCES, DIVORCE_RATIO, DIVORCED, OUTSIDE_SHARE, CAESAREAN_SHARE,
    DEATHS_PER_BIRTHS,
)  # fmt: skip

_MONTHS = [
    "Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου",
    "Ιουλίου", "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου",
]  # fmt: skip
_DATE = re.compile(r"Πειραιάς,\s+(\d{1,2})\s+(\w+)\s+(\d{4})")
_NUM = r"-?\d{1,3}(?:\.\d{3})*"  # Greek thousands separator
_TABLE1 = re.compile(rf"^(\d{{4}}) ({_NUM}) ({_NUM})(\*?) ({_NUM})$")
_PCT = r"-?\d+,\d%"
_TABLE2 = re.compile(rf"^(.+?) ({_NUM}) {_PCT} ({_NUM}) {_PCT}$")
_TABLE2_YEAR = re.compile(r"έτους (\d{4})")
_DEC = r"\d+,\d"
_TABLE7 = re.compile(rf"^(\d{{4}}) ({_NUM}) ({_NUM}) ({_NUM}) ({_DEC}) ({_DEC}) ({_DEC})$")
_TABLE7_BREAK = re.compile(r"^\* Το (\d{4}), το όριο βιωσιμότητας")  # noqa: RUF001
_OR_NONE = rf"({_NUM}|-) (?:{_DEC}|-)"
_TABLE8 = re.compile(rf"^(\d{{4}}) ({_NUM}) ({_NUM}) ({_NUM}) {_DEC} {_OR_NONE} {_OR_NONE}$")
_BY_TWO = re.compile(rf"^(.+?) ({_NUM}) {_DEC} ({_NUM}) {_DEC}$")  # two (count, %) columns
_GRAPH3 = re.compile(rf"^(\d{{4}}) ({_DEC}) ({_DEC})$")  # year, normal %, caesarean %
# Age labels that are not "a-b" or "a+" (provenance.AGE_PATTERN)
_AGE = {"<15": "0-14", "<20": "0-19", "Άγνωστη": "unknown", "Κάτω του έτους": "0"}
_TABLE5 = {"Φυσιολογικός τοκετός": NORMAL_DELIVERY, "Καισαρική Τομή": CAESAREAN}
_TABLE11 = {
    "type": ("Συναινετικά", "Κατ’ αντιδικία", "Δεν δηλώθηκε"),  # noqa: RUF001
    "duration": ("Έως 2 έτη", "2 - 4 έτη", "5 - 9 έτη", "10+ έτη"),
}
_TABLE4 = {
    "Γεννήσεις ζώντων": "total",
    "Αγόρια": "male",
    "Κορίτσια": "female",
    "Ελληνίδες μητέρες": "greek",
    "Αλλοδαπές μητέρες": "foreign",
    "Μη δηλωθείσα ιθαγένεια": "undeclared",
    "Γεννήσεις εντός γάμου/συμφώνου συμβίωσης": "inside",
    "Γεννήσεις εκτός γάμου/συμφώνου συμβίωσης": "outside",
}


def _int(text: str) -> int:
    return int(text.replace(".", ""))


def pages(pdf: bytes) -> list[str]:
    """The text of each page, line by line as printed."""
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return [page.extract_text() or "" for page in doc.pages]


def release_date(text: list[str]) -> str:
    """The date on the first page, ISO 8601: the vintage of every value."""
    m = _DATE.search(text[0])
    if not m or m.group(2) not in _MONTHS:
        raise ValueError("no release date 'Πειραιάς, <day> <month> <year>' on page 1")
    return f"{m.group(3)}-{_MONTHS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"


def _table(text: list[str], title: str) -> list[str]:
    found = [p for p in text if title in p]
    if len(found) != 1:
        raise ValueError(f"'{title}' on {len(found)} pages, expected one")
    lines = found[0].splitlines()
    start = next(i for i, line in enumerate(lines) if title in line)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(("Πίνακας ", "Γράφημα "))),
        len(lines),
    )
    return lines[start:end]


def _cells(line: str, n: int) -> tuple[str, list[int]] | None:
    """A row's label and its last n counts ("-" is none), or None for any other line."""
    tokens = line.split()
    values = tokens[len(tokens) - n :]
    if len(values) < n or not all(v == "-" or re.fullmatch(_NUM, v) for v in values):
        return None
    return " ".join(tokens[: len(tokens) - n]), [0 if v == "-" else _int(v) for v in values]


def _years(lines: list[str], n: int) -> list[str]:
    """The column heading of n years."""
    for line in lines:
        tokens = line.split()
        if len(tokens) == n and all(re.fullmatch(r"\d{4}", t) for t in tokens):
            return tokens
    raise ValueError(f"no heading of {n} years in {lines[0]!r}")


def _rows(lines: list[str], n: int) -> dict[str, list[int]]:
    rows: dict[str, list[int]] = {}
    for line in lines:
        if cells := _cells(line, n):
            if cells[0] in rows:
                raise ValueError(f"{lines[0]!r}: row {cells[0]!r} twice")
            rows[cells[0]] = cells[1]
    return rows


def _check(what: str, ours: object, theirs: object) -> None:
    if ours != theirs:
        raise ValueError(f"{what}: {ours} != {theirs}")


def _percent(part: int, whole: int) -> float:
    """part / whole in %, to one decimal, half up, as ELSTAT rounds (Tables 7 and 10)."""
    return int(part * 1000 / whole + 0.5) / 10


def _decimal(text: str) -> float:
    return float(text.replace(",", "."))


def table1(text: list[str]) -> pl.DataFrame:
    """Greece by year: births, deaths, natural change, and whether deaths are revised."""
    lines = _table(text, "Πίνακας 1.")
    rows = [m.groups() for line in lines if (m := _TABLE1.match(line.strip()))]
    if not rows:
        raise ValueError("Table 1: no year rows")
    marked = any(r[3] for r in rows)
    note = next((line for line in lines if line.startswith("*")), "")
    if marked and "αναθεωρ" not in note:
        raise ValueError(f"Table 1: '*' marks a value but the note is not a revision: {note!r}")
    df = pl.DataFrame(
        [(y, _int(b), _int(d), bool(star), _int(n)) for y, b, d, star, n in rows],
        schema=["period", "births", "deaths", "revised", "natural_change"],
        orient="row",
    )
    wrong = df.filter(pl.col("births") - pl.col("deaths") != pl.col("natural_change"))
    if wrong.height:
        raise ValueError(f"Table 1: births minus deaths differ from natural change:\n{wrong}")
    return df


def table2(text: list[str]) -> tuple[str, pl.DataFrame]:
    """The year of Table 2, and its rows: label, births, deaths, in printed order."""
    lines = _table(text, "Πίνακας 2.")
    year = _TABLE2_YEAR.search(" ".join(lines[:3]))
    if not year:
        raise ValueError("Table 2: no 'έτους YYYY' in its title")
    rows = [m.groups() for line in lines if (m := _TABLE2.match(line.strip()))]
    df = pl.DataFrame(
        [(label, _int(b), _int(d)) for label, b, d in rows],
        schema=["label_el", "births", "deaths"],
        orient="row",
    )
    return year.group(1), df


def _long(rows: Sequence[tuple[str, str, str, str, float]], **fixed: object) -> pl.DataFrame:
    """(period, sex, age, definition_id, value) rows of Greece with the other columns."""
    df = pl.DataFrame(
        rows, schema=["period", "sex", "age", "definition_id", "value"], orient="row"
    ).with_columns(pl.col("value").cast(pl.Float64))
    defaults = {"nature": Nature.OBSERVED.value, "revised": False, "break_in_series": False}
    columns = {k: pl.lit(v) for k, v in {**defaults, **fixed}.items()}
    return df.with_columns(geo_code=pl.lit("EL"), **columns)


def table3(text: list[str], births: dict[str, int]) -> pl.DataFrame:
    """Births by the mother's age group, checked against their total and Table 1."""
    lines = _table(text, "Πίνακας 3.")
    years = _years(lines, 5)
    rows = _rows(lines, 5)
    total = rows.pop("Σύνολο")
    for i, year in enumerate(years):
        _check(f"Table 3 {year}: age groups", sum(v[i] for v in rows.values()), total[i])
        _check(f"Table 3 {year}: total", total[i], births[year])
    t = Sex.TOTAL.value
    return _long(
        [(y, t, _AGE.get(a, a), BIRTHS, v[i]) for a, v in rows.items() for i, y in enumerate(years)]
    )


def table4(text: list[str], births: dict[str, int]) -> pl.DataFrame:
    """Births by sex, by mother's citizenship, outside marriage, checked to add up."""
    lines = _table(text, "Πίνακας 4.")
    years = _years(lines, 5)
    rows = _rows(lines, 5)
    _check("Table 4: rows", sorted(rows), sorted(_TABLE4))
    r = {_TABLE4[k]: v for k, v in rows.items()}
    for i, year in enumerate(years):
        _check(f"Table 4 {year}: total", r["total"][i], births[year])
        _check(f"Table 4 {year}: boys + girls", r["male"][i] + r["female"][i], r["total"][i])
        _check(
            f"Table 4 {year}: Greek + foreign + undeclared",
            r["greek"][i] + r["foreign"][i] + r["undeclared"][i],
            r["total"][i],
        )
        inside, outside = r["inside"][i], r["outside"][i]
        _check(f"Table 4 {year}: inside + outside", inside + outside, r["total"][i])
    # the "% Συμμετοχή" line right below the births outside marriage
    outside_row = next(i for i, line in enumerate(lines) if line.startswith("Γεννήσεις εκτός"))
    share = lines[outside_row + 1].split()
    _check("Table 4: share outside marriage, label", share[:2], ["%", "Συμμετοχή"])
    printed = [_decimal(v) for v in share[2:]]
    _check("Table 4: share outside marriage, values", len(printed), len(years))
    for i, year in enumerate(years):
        ours = _percent(r["outside"][i], r["total"][i])
        _check(f"Table 4 {year}: share outside marriage", ours, printed[i])
    t, y5 = Sex.TOTAL.value, list(enumerate(years))
    return pl.concat(
        [
            _long(
                [
                    (y, sex, AGE_TOTAL, BIRTHS, r[sex][i])
                    for sex in ("male", "female")
                    for i, y in y5
                ]
                + [(y, t, AGE_TOTAL, FOREIGN_MOTHER, r["foreign"][i]) for i, y in y5]
                + [(y, t, AGE_TOTAL, OUTSIDE_MARRIAGE, r["outside"][i]) for i, y in y5]
            ),
            _long(
                [(y, t, AGE_TOTAL, OUTSIDE_SHARE, printed[i]) for i, y in y5],
                nature=Nature.OFFICIAL_ESTIMATE.value,
            ),
        ]
    )


def table6(text: list[str], deaths: dict[str, int]) -> pl.DataFrame:
    """Deaths by sex and age group, checked to add up by sex and age, and against Table 1.
    The total of both sexes and all ages is Table 1's, so it is not repeated."""
    lines = _table(text, "Πίνακας 6.")
    years = _years(lines, 2)
    rows = _rows(lines, 6)
    total = rows.pop("")
    sexes = (Sex.TOTAL.value, Sex.MALE.value, Sex.FEMALE.value)
    out: list[tuple[str, str, str, str, float]] = []
    for i, year in enumerate(years):
        _check(f"Table 6 {year}: total", total[3 * i], deaths[year])
        for a, v in rows.items():
            _check(f"Table 6 {year} {a}: men + women", v[3 * i + 1] + v[3 * i + 2], v[3 * i])
        for j, sex in enumerate(sexes):
            k = 3 * i + j
            _check(f"Table 6 {year} {sex}: age groups", sum(v[k] for v in rows.values()), total[k])
            out += [(year, sex, _AGE.get(a, a), DEATHS, v[k]) for a, v in rows.items()]
            if sex != Sex.TOTAL.value:
                out.append((year, sex, AGE_TOTAL, DEATHS, total[k]))
    return _long(out)


def table7(text: list[str], births: dict[str, int], infant_deaths: dict[str, int]) -> pl.DataFrame:
    """Stillbirths, infant deaths (those of Table 6's years are not repeated) and the
    infant, perinatal and neonatal mortality rates; the break its footnote names."""
    lines = _table(text, "Πίνακας 7.")
    if "Βρεφικής Περιγεννητικής Νεογνικής" not in "\n".join(lines):
        raise ValueError("Table 7: rate columns not in the order infant, perinatal, neonatal")
    breaks = {m.group(1) for line in lines if (m := _TABLE7_BREAK.match(line))}
    if len(breaks) != 1:
        raise ValueError("Table 7: no footnote naming the year of the stillbirth break")
    t = Sex.TOTAL.value
    counts: list[tuple[str, str, str, str, float]] = []
    rates: list[tuple[str, str, str, str, float]] = []
    for line in lines:
        if not (m := _TABLE7.match(line.strip())):
            continue
        year = m.group(1)
        born, still, infant = (_int(g) for g in m.groups()[1:4])
        infant_rate, perinatal, neonatal = (float(g.replace(",", ".")) for g in m.groups()[4:])
        _check(f"Table 7 {year}: births", born, births[year])
        # ELSTAT rounds half up, to one decimal
        ours = int(infant * 10_000 / born + 0.5) / 10
        _check(f"Table 7 {year}: infant mortality", ours, infant_rate)
        if year in infant_deaths:
            _check(f"Table 7 {year}: infant deaths", infant, infant_deaths[year])
        else:
            counts.append((year, t, "0", DEATHS, infant))
        counts.append((year, t, AGE_TOTAL, STILLBIRTHS, still))
        rates += [
            (year, t, AGE_TOTAL, INFANT_RATE, infant_rate),
            (year, t, AGE_TOTAL, PERINATAL_RATE, perinatal),
            (year, t, AGE_TOTAL, NEONATAL_RATE, neonatal),
        ]
    if not counts:
        raise ValueError("Table 7: no year rows")
    (year,) = breaks
    df = pl.concat([_long(counts), _long(rates, nature=Nature.OFFICIAL_ESTIMATE.value)])
    broken = pl.col("definition_id").is_in([STILLBIRTHS, PERINATAL_RATE])
    return df.with_columns(break_in_series=(pl.col("period") == year) & broken)


def table5(text: list[str], births: dict[str, int]) -> pl.DataFrame:
    """Births by delivery method, checked against Table 1 with the undeclared ones."""
    lines = _table(text, "Πίνακας 5.")
    years = _years(lines, 5)
    rows = _rows(lines, 5)
    _check("Table 5: rows", sorted(rows), sorted([*_TABLE5, "Δεν δηλώθηκε"]))
    for i, year in enumerate(years):
        _check(f"Table 5 {year}: methods", sum(v[i] for v in rows.values()), births[year])
    # Graph 3 prints each year's shares of all births: normal, caesarean
    shares = {
        m[1]: (_decimal(m[2]), _decimal(m[3]))
        for line in _table(text, "Γράφημα 3.")
        if (m := _GRAPH3.match(line.strip()))
    }
    _check("Graph 3: years", sorted(shares), sorted(years))
    for i, year in enumerate(years):
        normal = _percent(rows["Φυσιολογικός τοκετός"][i], births[year])
        caesarean = _percent(rows["Καισαρική Τομή"][i], births[year])
        _check(f"Graph 3 {year}: normal, caesarean %", (normal, caesarean), shares[year])
    t = Sex.TOTAL.value
    return pl.concat(
        [
            _long(
                [
                    (y, t, AGE_TOTAL, d, rows[k][i])
                    for k, d in _TABLE5.items()
                    for i, y in enumerate(years)
                ]
            ),
            _long(
                [(y, t, AGE_TOTAL, CAESAREAN_SHARE, shares[y][1]) for y in years],
                nature=Nature.OFFICIAL_ESTIMATE.value,
            ),
        ]
    )


def table8(text: list[str]) -> pl.DataFrame:
    """Marriages, civil marriages and civil partnerships by year, checked to add up."""
    lines = _table(text, "Πίνακας 8.")
    if "Θρησκευτικοί Πολιτικοί Σύμφωνα Συμβίωσης" not in "\n".join(lines):
        raise ValueError("Table 8: columns not in the order religious, civil, partnerships")
    t = Sex.TOTAL.value
    out: list[tuple[str, str, str, str, float]] = []
    for line in lines:
        if not (m := _TABLE8.match(line.strip())):
            continue
        year, both, married, religious = m.group(1), *(_int(g) for g in m.groups()[1:4])
        civil, partners = (None if g == "-" else _int(g) for g in m.groups()[4:])
        _check(f"Table 8 {year}: religious + civil", religious + (civil or 0), married)
        _check(f"Table 8 {year}: marriages + partnerships", married + (partners or 0), both)
        out.append((year, t, AGE_TOTAL, MARRIAGES, married))
        out += [
            (year, t, AGE_TOTAL, d, v)
            for d, v in ((CIVIL_MARRIAGES, civil), (PARTNERSHIPS, partners))
            if v is not None
        ]
    if not out:
        raise ValueError("Table 8: no year rows")
    return _long(out)


_SEXES = (Sex.MALE.value, Sex.FEMALE.value)  # the columns "Άνδρες Γυναίκες"


def _by_two(lines: list[str], heading: str) -> dict[str, tuple[int, int]]:
    """Rows of two (count, %) columns under ``heading``: label -> the two counts."""
    if not any(line.strip() == heading for line in lines[1:3]):
        raise ValueError(f"{lines[0]!r}: columns not {heading!r}")
    rows = {
        m.group(1): (_int(m.group(2)), _int(m.group(3)))
        for line in lines
        if (m := _BY_TWO.match(line.strip()))
    }
    if not rows:
        raise ValueError(f"{lines[0]!r}: no rows")
    return rows


def _year(lines: list[str], latest: str) -> str:
    year = _TABLE2_YEAR.search(lines[0])
    if not year or year.group(1) != latest:
        raise ValueError(f"{lines[0]!r}: not of the latest year, {latest}")
    return year.group(1)


def table9(text: list[str], latest: str) -> pl.DataFrame:
    """Spouses at their first marriage by sex and age group, checked to add up by sex."""
    lines = _table(text, "Πίνακας 9.")
    year, rows = _year(lines, latest), _by_two(lines, "Άνδρες Γυναίκες")
    total = rows.pop("Σύνολα")
    for j, sex in enumerate(_SEXES):
        _check(f"Table 9 {sex}: age groups", sum(v[j] for v in rows.values()), total[j])
    return _long(
        [(year, s, AGE_TOTAL, FIRST_MARRIAGES, total[j]) for j, s in enumerate(_SEXES)]
        + [
            (year, s, _AGE.get(a, a), FIRST_MARRIAGES, v[j])
            for a, v in rows.items()
            for j, s in enumerate(_SEXES)
        ]
    )


def table10(text: list[str], marriages: dict[str, int]) -> pl.DataFrame:
    """Divorces and divorces per 100 marriages, checked against Table 8's marriages."""
    lines = _table(text, "Πίνακας 10.")
    years = _years(lines, 5)
    divorces = _rows(lines, 5)["Διαζύγια"]
    label = "Διαζύγια ανά 100 γάμους "
    ratio = next((line[len(label) :].split() for line in lines if line.startswith(label)), [])
    _check("Table 10: divorces per 100 marriages, values", len(ratio), 5)
    t, counts, rates = Sex.TOTAL.value, [], []
    for i, year in enumerate(years):
        printed = float(ratio[i].replace(",", "."))
        ours = int(divorces[i] * 1000 / marriages[year] + 0.5) / 10  # half up, as Table 7
        _check(f"Table 10 {year}: divorces per 100 marriages", ours, printed)
        counts.append((year, t, AGE_TOTAL, DIVORCES, divorces[i]))
        rates.append((year, t, AGE_TOTAL, DIVORCE_RATIO, printed))
    return pl.concat([_long(counts), _long(rates, nature=Nature.OFFICIAL_ESTIMATE.value)])


def table11(text: list[str], divorces: dict[str, int]) -> None:
    """Divorces by type and by duration of the marriage, each adding up to Table 10."""
    lines = _table(text, "Πίνακας 11.")
    years = _years(lines, 2)
    rows = _by_two(lines, " ".join(years))
    _check(
        "Table 11: rows", sorted(rows), sorted(["Σύνολο", *_TABLE11["type"], *_TABLE11["duration"]])
    )
    for i, year in enumerate(years):
        _check(f"Table 11 {year}: total", rows["Σύνολο"][i], divorces[year])
        for by, labels in _TABLE11.items():
            _check(f"Table 11 {year}: {by}", sum(rows[k][i] for k in labels), divorces[year])


def table12(text: list[str], divorces: dict[str, int], latest: str) -> pl.DataFrame:
    """Divorced persons by sex and age group: two per divorce of Table 10."""
    lines = _table(text, "Πίνακας 12.")
    year, rows = _year(lines, latest), _by_two(lines, "Άνδρες Γυναίκες")
    _check(f"Table 12 {year}: men + women", sum(sum(v) for v in rows.values()), 2 * divorces[year])
    return _long(
        [
            (year, s, _AGE.get(a, a), DIVORCED, v[j])
            for a, v in rows.items()
            for j, s in enumerate(_SEXES)
        ]
    )


def _areas(rows: pl.DataFrame) -> pl.DataFrame:
    """Rows of Table 2 with their NUTS code and level, after the adds-up checks."""
    areas = pl.read_csv(REFERENCE / "elstat_areas_el.csv", schema_overrides={"geo_code": pl.String})
    unknown = set(rows["label_el"]) - set(areas["label_el"])
    missing = set(areas["label_el"]) - set(rows["label_el"])
    if unknown or missing or rows["label_el"].is_duplicated().any():
        raise ValueError(f"Table 2: labels unknown {sorted(unknown)}, missing {sorted(missing)}")
    df = rows.join(areas, on="label_el").with_columns(level=pl.col("geo_code").str.len_chars() - 2)
    counts = ["births", "deaths"]
    country = df.filter(pl.col("geo_code") == "EL").select(counts)
    regions = df.filter((pl.col("level") == 2) | pl.col("geo_code").is_null()).select(counts).sum()
    if not country.equals(regions):
        raise ValueError(
            f"Table 2: regions and abroad {regions.row(0)} != country {country.row(0)}"
        )
    units = (
        df.filter(pl.col("level") == 3)
        .group_by(parent=pl.col("geo_code").str.head(4))
        .agg(pl.col(c).sum().alias(f"{c}_units") for c in counts)
        .join(df, left_on="parent", right_on="geo_code")
        .filter(
            (pl.col("births") != pl.col("births_units"))
            | (pl.col("deaths") != pl.col("deaths_units"))
        )
    )
    if units.height:
        raise ValueError(f"Table 2: regional units do not add up to their region:\n{units}")
    return df


def _yearly(df: pl.DataFrame, definition_id: str) -> dict[str, int]:
    one = df.filter(pl.col("definition_id") == definition_id)
    return dict(one.select("period", pl.col("value").cast(pl.Int64)).iter_rows())


def to_observations(snapshot: Snapshot, pdf: bytes) -> pl.DataFrame:
    """Every value the module reads (see its docstring), once."""
    text = pages(pdf)
    national = table1(text)
    year, rows = table2(text)
    areas = _areas(rows)
    if (
        not areas.filter(pl.col("geo_code") == "EL")
        .select("births", "deaths")
        .equals(national.filter(pl.col("period") == year).select("births", "deaths"))
    ):
        raise ValueError(f"Table 2: the country row differs from Table 1 for {year}")
    regional = (
        areas.filter(pl.col("level") >= 2)
        .group_by("geo_code")
        .agg(pl.col("births", "deaths").sum(), merged=pl.len() > 1)
        .with_columns(
            period=pl.lit(year),
            nature=pl.when("merged")
            .then(pl.lit(Nature.DERIVED.value))
            .otherwise(pl.lit(Nature.OBSERVED.value)),
            revised=pl.lit(False),
        )
    )
    births = dict(national.select("period", "births").iter_rows())
    deaths = dict(national.select("period", "deaths").iter_rows())
    by_age = table6(text, deaths)
    infant = by_age.filter((pl.col("age") == "0") & (pl.col("sex") == Sex.TOTAL.value))
    infant_deaths = dict(infant.select("period", pl.col("value").cast(pl.Int64)).iter_rows())
    nuptiality = table8(text)
    marriages = _yearly(nuptiality, MARRIAGES)
    divorce = table10(text, marriages)
    divorces = _yearly(divorce, DIVORCES)
    table11(text, divorces)
    tables = [
        table3(text, births),
        table4(text, births),
        table5(text, births),
        by_age,
        table7(text, births, infant_deaths),
        nuptiality,
        table9(text, year),
        divorce,
        table12(text, divorces, year),
    ]
    long = pl.concat(
        [
            national.select(
                "period",
                geo_code=pl.lit("EL"),
                definition_id=pl.lit(d),
                value=c,
                nature=pl.lit(Nature.OBSERVED.value),
                revised=pl.col("revised") if c != "births" else pl.lit(False),
            )
            for d, c in ((BIRTHS, "births"), (DEATHS, "deaths"), (NATURAL_CHANGE, "natural_change"))
        ]
        + [
            regional.select(
                "period",
                "geo_code",
                definition_id=pl.lit(d),
                value=c,
                nature="nature",
                revised="revised",
            )
            for d, c in ((BIRTHS, "births"), (DEATHS, "deaths"))
        ]
        # deaths per 100 live births: the country every year of Table 1, the regions and
        # NUTS 3 regions the year of Table 2
        + [
            df.select(
                "period",
                "geo_code",
                definition_id=pl.lit(DEATHS_PER_BIRTHS),
                value=100 * pl.col("deaths") / pl.col("births"),
                nature=pl.lit(Nature.DERIVED.value),
                revised="revised",
            )
            for df in (national.with_columns(geo_code=pl.lit("EL")), regional)
        ],
        how="vertical_relaxed",  # counts and the ratio in one value column
    ).with_columns(
        sex=pl.lit(Sex.TOTAL.value), age=pl.lit(AGE_TOTAL), break_in_series=pl.lit(False)
    )
    columns = long.columns
    long = pl.concat(
        [long.with_columns(pl.col("value").cast(pl.Float64))] + [t.select(columns) for t in tables]
    )
    source = get_source(SOURCE_ID)
    metric = {d: get_definition(d).metric for d in DEFINITIONS}
    unit = {d: get_definition(d).unit for d in DEFINITIONS}
    return long.select(
        metric=pl.col("definition_id").replace_strict(metric),
        definition_id="definition_id",
        geo_code="geo_code",
        geo_vintage=pl.lit("NUTS2024"),
        period="period",
        sex="sex",
        age="age",
        value=pl.col("value").cast(pl.Float64),
        unit=pl.col("definition_id").replace_strict(unit),
        source=pl.lit(source.provider),
        dataset_code=pl.lit(source.dataset_code),
        source_url=pl.lit(snapshot.source_url),
        vintage=pl.lit(release_date(text)),
        retrieved_at=pl.lit(snapshot.retrieved_at, dtype=pl.Datetime("us", "UTC")),
        transform_version=pl.lit(TRANSFORM_VERSION),
        nature="nature",
        status=pl.when("revised")
        .then(pl.lit(Status.REVISED.value))
        .otherwise(pl.lit(Status.FINAL.value)),
        break_in_series="break_in_series",
        scenario_id=pl.lit(None, dtype=pl.String),
        interval=pl.lit(None, dtype=pl.String),
    ).sort("definition_id", "geo_code", "period", "sex", "age")
