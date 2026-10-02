// Choropleth and proportional symbols on illustrative square "regions" (not GISCO data).
import assert from "node:assert/strict";
import { test } from "node:test";
import { choropleth, symbols } from "../src/map.js";
import { GEOMETRY } from "../visual/gallery.js";
import { attr, document, marks, row, tokens } from "./rows.js";

const CODES = GEOMETRY.features.map((f) => f.id);
const rate = (extra = {}) =>
  CODES.map((geo, i) => row(geo, "2024", 8 + i / 2, { unit: "per 1000 average population", ...(extra[geo] ?? {}) }));
const counts = CODES.map((geo, i) => row(geo, "2024", (i + 1) * 100000));
const SPEC = { title: "Η Αττική έχει τον υψηλότερο δείκτη", focus: "EL30", geometry: GEOMETRY, labels: { EL30: "Αττική", EL41: "Βόρειο Αιγαίο" } };
const map = (type, rows, spec = SPEC) => type(rows, spec, { tokens, document });

test("a choropleth fills each region from the palette and names the classification", () => {
  const { figure } = map(choropleth, rate());
  const fills = [...figure.querySelectorAll('g[data-mark="geo"] path[fill]')].map((p) => p.getAttribute("fill"));
  assert.equal(fills.length, CODES.length);
  for (const f of fills) assert.ok(tokens["palette-sequential"].includes(f), f);
  assert.ok(figure.textContent.includes("ανά 1.000 κατοίκους (μέσος πληθυσμός) (ίσα διαστήματα)"));
});

test("every map credits the geometry's source in its footer", () => {
  for (const [type, rows] of [[choropleth, rate()], [symbols, counts]])
    assert.ok(map(type, rows).figure.querySelector("figcaption").textContent.endsWith(` · ${GEOMETRY.attribution}`));
});

test("the focus region is outlined in the accent", () => {
  const outlines = marks(map(choropleth, rate()).figure, "geo").filter((g) => attr(g, "stroke") === tokens["color-accent"]);
  assert.equal(outlines.length, 1);
  assert.equal(outlines[0].querySelectorAll("path").length, 1);
});

test("rings are rewound so a region is not drawn as the whole globe", () => {
  const ccw = structuredClone(GEOMETRY);
  for (const f of ccw.features) f.geometry.coordinates = f.geometry.coordinates.map((r) => [...r].reverse());
  const area = (fig) => [...fig.querySelectorAll('g[data-mark="geo"] path')].map((p) => p.getAttribute("d").length);
  assert.deepEqual(area(map(choropleth, rate(), { ...SPEC, geometry: ccw }).figure), area(map(choropleth, rate()).figure));
});

test("projected values get a dashed boundary; provisional ones a hollow marker", () => {
  const { figure } = map(choropleth, rate({ EL41: { nature: "projected" }, EL42: { status: "provisional" } }));
  assert.ok(marks(figure, "geo").some((g) => attr(g, "stroke-dasharray") === tokens["stroke-dash-projected"]));
  assert.equal(figure.querySelectorAll('g[data-mark="dot"] circle').length, 1);
});

test("a choropleth refuses counts; symbols refuse rates", () => {
  assert.throws(() => map(choropleth, counts), /rates only/);
  assert.throws(() => map(symbols, rate()), /counts/);
});

test("symbol area is proportional to the value, the focus in the accent, with a size key", () => {
  const { figure } = map(symbols, counts);
  const [dots, ...key] = marks(figure, "dot");
  const circles = [...dots.querySelectorAll("circle")];
  assert.equal(circles.length, CODES.length);
  const r = circles.map((c) => +c.getAttribute("r")).sort((a, b) => b - a);
  assert.ok(Math.abs((r[0] / r[3]) ** 2 - 13 / 10) < 0.01, "area ∝ value");
  assert.ok(circles.some((c) => c.getAttribute("fill") === tokens["color-accent"]));
  assert.equal(key.length, 2);
});

test("alt text gives the highest and lowest region and the regions without a value", () => {
  const rows = rate({ EL43: { value: null, status: "not_available" } });
  const { alt } = map(choropleth, rows);
  assert.equal(alt, "Η Αττική έχει τον υψηλότερο δείκτη. 2024: υψηλότερη τιμή EL42 13,5; χαμηλότερη τιμή EL53 8; μη διαθέσιμη: EL43.");
});

test("maps refuse geometry without attribution, unknown regions and intervals", () => {
  const { attribution, ...bare } = GEOMETRY;
  assert.throws(() => map(choropleth, rate(), { ...SPEC, geometry: bare }), /attribution/);
  assert.throws(() => map(choropleth, [...rate(), row("EL99", "2024", 1, { unit: "per 1000 average population" })]), /no geometry for EL99/);
  assert.throws(() => map(choropleth, [...rate(), row("EL30", "2024", 1, { unit: "per 1000 average population", interval: "95_lower" })]), /central values/);
});
