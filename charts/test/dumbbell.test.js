// The dumbbell: two periods per area, sorted, focus in the accent, grammar on the second
// value. The rows are hand-written, not data.
import assert from "node:assert/strict";
import { test } from "node:test";
import { dumbbell } from "../src/dumbbell.js";
import { attr, document, marks, row, tokens } from "./rows.js";

const ROWS = [
  row("EL", "2011", 1.4),
  row("EL", "2024", 1.24, { status: "provisional" }),
  row("PT", "2011", 1.35),
  row("PT", "2024", 1.4),
  row("IT", "2011", 1.44),
  row("IT", "2024", 1.18),
];
const SPEC = { title: "Η γονιμότητα έπεσε στην Ελλάδα και στην Ιταλία", labels: { EL: "Ελλάδα", PT: "Πορτογαλία", IT: "Ιταλία" } };
const chart = (rows = ROWS, spec = SPEC) => dumbbell(rows, spec, { tokens, document });

test("areas are sorted by the second value, the focus in the accent, comparators neutral", () => {
  const { figure } = chart();
  const ticks = [...figure.querySelectorAll('g[data-mark="y-axis tick label"] text')].map((t) => t.textContent);
  assert.deepEqual(ticks, ["Πορτογαλία", "Ελλάδα", "Ιταλία"]);
  const strokes = marks(figure, "link").map((g) => attr(g, "stroke"));
  assert.ok(strokes.includes(tokens["color-accent"]) && strokes.includes(tokens["color-comparator"]));
});

test("the two years are labelled on the focus' row and a provisional second value is hollow", () => {
  const { figure } = chart();
  assert.ok(figure.textContent.includes("2011") && figure.textContent.includes("2024"));
  const fills = [...marks(figure, "dot")[1].querySelectorAll("circle")].map((c) => c.getAttribute("fill"));
  assert.ok(fills.includes(tokens["color-background"]));
});

test("a projected second value draws a dashed link", () => {
  const rows = [row("EL", "2024", 10), row("EL", "2050", 8, { nature: "projected" })];
  const [link] = marks(chart(rows).figure, "link");
  assert.equal(attr(link, "stroke-dasharray"), String(tokens["stroke-dash-projected"]));
});

test("alt text gives each area from its first to its second value", () => {
  const { alt } = chart();
  assert.ok(alt.startsWith("Η γονιμότητα έπεσε στην Ελλάδα και στην Ιταλία. Ελλάδα: από 1,4 (2011) σε 1,24 (2024)"));
});

test("it needs two periods, one value each, and no scenarios or bounds", () => {
  assert.throws(() => chart([...ROWS, row("EL", "2020", 1.3)]), /two periods/);
  assert.throws(() => chart(ROWS.slice(1)), /EL: needs one value/);
  assert.throws(() => chart([row("EL", "2011", 1), row("EL", "2024", 1, { nature: "scenario", scenario_id: "x" })]), /not scenarios/);
});
