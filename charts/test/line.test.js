// The line chart and the composite every chart returns: figure, table, alt text, CSV.
// The rows are hand-written, not data.
import assert from "node:assert/strict";
import { test } from "node:test";
import { line } from "../src/line.js";
import { NATURES, STATUSES, style } from "../src/grammar.js";
import { MODES, document, marks, row, tokens } from "./rows.js";

const ROWS = [
  row("EL", "2011", 11123392),
  row("EL", "2012", 11086406, { break_in_series: true }),
  row("EL", "2013", null, { status: "not_available" }),
  row("EL", "2014", -1234.5, { status: "provisional" }),
  row("EL", "2015", 11000000, { nature: "projected" }),
  row("EL", "2016", 10900000, { nature: "scenario", scenario_id: "low" }),
  row("PT", "2011", 10557560),
  row("PT", "2014", 10401062),
];
const SPEC = { title: "Ο πληθυσμός μειώνεται", labels: { EL: "Ελλάδα", PT: "Πορτογαλία" } };
const chart = (rows = ROWS, spec = SPEC) => line(rows, spec, { tokens, document });

const paths = (fig) => marks(fig, "line");

test("every token the grammar names exists in every mode", () => {
  for (const nature of NATURES)
    for (const status of STATUSES) {
      const { dash, color } = style(nature, status);
      for (const name of [dash, color].filter(Boolean))
        for (const [mode, t] of Object.entries(MODES)) assert.ok(name in t, `${name} in ${mode}`);
    }
});

test("the figure carries the finding as title; the footer gives source, dataset, vintage, nature and breaks", () => {
  const { figure } = chart();
  assert.equal(figure.querySelector("h2").textContent, SPEC.title);
  assert.equal(
    figure.querySelector("figcaption").textContent,
    "Πηγή: eurostat · demo_gind · έκδοση 2026-09-15 · παρατήρηση, προβολή, σενάριο · * διακοπή σειράς: Ελλάδα 2012",
  );
});

test("the focus takes the accent, comparators the neutral colour, scenarios their own hue", () => {
  const strokes = paths(chart().figure).map((p) => p.getAttribute("stroke"));
  assert.ok(strokes.includes(tokens["color-accent"]));
  assert.ok(strokes.includes(tokens["color-comparator"]));
  assert.ok(strokes.includes(tokens["color-scenario"]));
});

test("projections are dashed, scenarios dotted, observations solid", () => {
  const dash = (stroke) => paths(chart().figure).filter((p) => p.getAttribute("stroke") === stroke).map((p) => p.getAttribute("stroke-dasharray"));
  assert.deepEqual(dash(tokens["color-comparator"]), [null]);
  assert.ok(dash(tokens["color-accent"]).includes(tokens["stroke-dash-projected"]));
  assert.deepEqual(dash(tokens["color-scenario"]), [tokens["stroke-dash-scenario"]]);
});

test("a break in series and a missing value leave gaps in the line", () => {
  const accent = paths(chart().figure).filter((p) => p.getAttribute("stroke") === tokens["color-accent"]);
  // 2011 | break | 2012, gap 2013, 2014 | projected 2014 to 2015
  assert.equal(accent.length, 3);
  const moves = accent.map((g) => (g.querySelector("path").getAttribute("d").match(/M/g) ?? []).length);
  assert.deepEqual(moves, [1, 2, 1]);
  assert.match(accent[2].querySelector("path").getAttribute("d"), /^M[^M]+L/, "the projection starts at the last value");
});

test("a comparator runs through its break in series, which keeps its mark", () => {
  const rows = [...ROWS, row("PT", "2012", 10500000, { break_in_series: true })];
  const comparator = paths(chart(rows).figure).filter((p) => p.getAttribute("stroke") === tokens["color-comparator"]);
  assert.equal(comparator.length, 1);
  assert.equal((comparator[0].querySelector("path").getAttribute("d").match(/M/g) ?? []).length, 1);
  assert.equal(marks(chart(rows).figure, "text").filter((g) => g.textContent === "*").length, 2);
});

test("a provisional value gets a hollow marker", () => {
  const dots = marks(chart().figure, "dot");
  assert.equal(dots.length, 1);
  assert.equal(dots[0].querySelectorAll("circle").length, 1);
  assert.equal(dots[0].getAttribute("fill"), tokens["color-background"]);
  assert.equal(dots[0].getAttribute("stroke"), tokens["color-accent"]);
});

test("labels sit on the lines instead of a legend", () => {
  const texts = [...chart().figure.querySelectorAll("text")].map((t) => t.textContent);
  assert.ok(texts.includes("Ελλάδα (low)"));
  assert.ok(texts.includes("Πορτογαλία"));
});

test("labels that would overlap are pushed apart and stay inside the plot", () => {
  const areas = ["PT", "IT", "ES", "FR", "DE", "AT"];
  const rows = [row("EL", "2011", 30), row("EL", "2012", 31), ...areas.map((g, i) => row(g, "2012", 10 + i / 10))];
  const svg = line(rows, SPEC, { tokens, document }).figure.querySelector("svg");
  const bottom = +svg.getAttribute("height") - 30; // Plot's default bottom margin
  const ys = marks(svg, "text")
    .map((g) => +g.querySelector("text").getAttribute("transform").match(/,([-\d.]+)\)/)[1])
    .sort((a, b) => a - b);
  assert.equal(ys.length, 7);
  for (let i = 1; i < ys.length; i++) assert.ok(ys[i] - ys[i - 1] > 11.99, `label positions ${ys}`);
  assert.ok(ys.at(-1) <= bottom, `lowest label at ${ys.at(-1)}, plot ends at ${bottom}`);
});

test("a scenario starts at the area's last value before it", () => {
  const [scenario] = paths(chart().figure).filter((g) => g.getAttribute("stroke") === tokens["color-scenario"]);
  assert.match(scenario.querySelector("path").getAttribute("d"), /^M[^M]+L[^M]+$/);
});

test("title, subtitle and footer take the design font and colours", () => {
  const { style } = chart().figure;
  assert.match(style.fontFamily, /Noto Sans/);
  assert.ok(style.background);
});

test("the table lists every row, formatted for reading", () => {
  const { table } = chart();
  assert.equal(table.querySelector("caption").textContent, SPEC.title);
  assert.equal(table.querySelectorAll("tbody tr").length, ROWS.length);
  const cells = [...table.querySelectorAll("tbody td")].map((td) => td.textContent);
  assert.ok(cells.includes("11.123.392"));
  assert.ok(cells.includes("−1.234,5"));
  assert.ok(cells.includes("μη διαθέσιμη"));
  assert.ok(cells.includes("low"));
  assert.ok(cells.includes("ναι"));
  const heads = [...table.querySelectorAll("th")].map((th) => th.textContent);
  assert.deepEqual(heads.slice(-2), ["Σενάριο", "Διακοπή σειράς"]);
});

test("alt text is derived from the data, focus first, scenarios named as such", () => {
  assert.equal(
    chart().alt,
    "Ο πληθυσμός μειώνεται. Ελλάδα: από 11.123.392 (2011) σε 11.000.000 (2015, προβολή); " +
      "Ελλάδα (σενάριο: low): από 10.900.000 (2016) σε 10.900.000 (2016); " +
      "Πορτογαλία: από 10.557.560 (2011) σε 10.401.062 (2014); προσωρινές τιμές: 2014; διακοπή σειράς: Ελλάδα 2012.",
  );
  const high = row("EL", "2016", 11500000, { nature: "scenario", scenario_id: "high" });
  assert.ok(chart([...ROWS, high]).alt.includes("Ελλάδα (σενάριο: high): από 11.500.000 (2016)"));
});

test("the CSV holds the raw values of every row and column", () => {
  const lines = chart().csv.trimEnd().split("\n");
  assert.equal(lines[0], Object.keys(ROWS[0]).join(","));
  assert.equal(lines.length, ROWS.length + 1);
  assert.equal(lines[4].split(",")[4], "-1234.5");
  assert.equal(lines[3].split(",")[4], "");
  const quoted = line([row("EL", "2011", 1, { source: 'a, "b"' })], SPEC, { tokens, document }).csv;
  assert.ok(quoted.includes('"a, ""b"""'));
});

test("English charts use English text and number format", () => {
  const { alt } = chart(ROWS, { ...SPEC, locale: "en-GB", labels: { EL: "Greece", PT: "Portugal" } });
  assert.ok(alt.includes("Greece: from 11,123,392 (2011) to 11,000,000 (2015, projection)"));
});

test("bad input fails loudly", () => {
  assert.throws(() => chart([]), /at least one row/);
  assert.throws(() => chart([row("PT", "2011", 1)]), /focus EL/);
  assert.throws(() => chart([row("EL", "2011", 1), row("EL", "2012", 1, { unit: "%" })]), /no dual axes/);
  assert.throws(() => chart([row("EL", "2011", null)]), /null exactly when/);
  for (const bad of [undefined, Number.NaN, "5"]) assert.throws(() => chart([row("EL", "2011", bad)]), /finite number/);
  assert.throws(() => chart([row("EL", "2011", 1, { nature: "forecast" })]), /unknown nature/);
  assert.throws(() => chart(ROWS, { labels: {} }), /title states the finding/);
  const { source, ...partial } = row("EL", "2011", 1);
  assert.throws(() => chart([partial]), /lacks source/);
  assert.throws(() => line(ROWS, SPEC, { document }), /tokens/);
});

const FAN = [
  row("EL", "2023", 100),
  row("EL", "2024", 101),
  ...["2030", "2040"].flatMap((p, i) => [
    row("EL", p, 102 + i, { nature: "projected" }),
    ...[["95", 6], ["80", 3]].flatMap(([level, w]) => [
      row("EL", p, 102 + i - w * (i + 1), { nature: "projected", interval: `${level}_lower` }),
      row("EL", p, 102 + i + w * (i + 1), { nature: "projected", interval: `${level}_upper` }),
    ]),
  ]),
];

test("a projection with interval bounds is a fan: 95% and 80% bands opening at the last observation", () => {
  const { figure } = chart(FAN);
  const areas = marks(figure, "area");
  assert.deepEqual(
    areas.map((g) => g.getAttribute("fill-opacity")),
    [String(tokens["opacity-band-95"]), String(tokens["opacity-band-80"])],
  );
  for (const g of areas) {
    assert.equal(g.getAttribute("fill"), tokens["color-accent"]);
    // three points: the 2024 observation and two projected periods
    assert.equal((g.querySelector("path").getAttribute("d").match(/L/g) ?? []).length, 5);
  }
  const edges = paths(figure).filter((g) => g.getAttribute("stroke-width") === String(tokens["stroke-width-band-edge"]));
  assert.equal(edges.length, 2, "the 95% band has edge lines");
});

test("interval bounds are bands, never lines or labels; alt text names the 95% interval", () => {
  const { figure, alt, table } = chart(FAN);
  const accentLines = paths(figure).filter((g) => g.getAttribute("stroke-width") === String(tokens["stroke-width-focus"]));
  assert.equal(accentLines.length, 2, "observed and projected segments only");
  assert.ok(alt.includes("από 100 (2023) σε 103 (2040, προβολή, 95%: 91–115)"), alt);
  assert.equal(table.querySelectorAll("tbody tr").length, FAN.length);
  const cells = [...table.querySelectorAll("td")].map((td) => td.textContent);
  assert.ok(cells.includes("κάτω όριο 95%"));
  assert.ok(cells.includes("κεντρική τιμή"));
});

test("the last observation before a projection is marked with its date", () => {
  const texts = marks(chart(FAN).figure, "text").map((g) => g.textContent);
  assert.ok(texts.includes("τελευταία παρατήρηση 2024"), texts.join("|"));
  assert.equal(marks(chart(FAN).figure, "rule").length, 1);
  assert.equal(marks(chart(ROWS.filter((r) => r.nature === "observed")).figure, "rule").length, 0);
});

test("a break in series carries the footnote mark on the figure", () => {
  const texts = marks(chart().figure, "text").map((g) => g.textContent);
  assert.ok(texts.includes("*"));
});

test("bands open at the last central value when bounds start later than the projection", () => {
  const sparse = FAN.filter((r) => !(r.interval && r.period === "2030"));
  const [band95] = marks(chart(sparse).figure, "area");
  // 2030 (projected, no bounds) then 2040
  assert.equal((band95.querySelector("path").getAttribute("d").match(/L/g) ?? []).length, 3);
});

test("a new nature continues from the last available value, not from a gap", () => {
  const rows = [row("EL", "2023", 100), row("EL", "2024", null, { status: "not_available" }), row("EL", "2030", 102, { nature: "projected" })];
  const dashed = paths(chart(rows).figure).filter((g) => g.getAttribute("stroke-dasharray") === tokens["stroke-dash-projected"]);
  assert.match(dashed[0].querySelector("path").getAttribute("d"), /^M[^M]+L[^M]+$/);
});
