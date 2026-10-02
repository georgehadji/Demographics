// The pyramid: sides, outline comparison, grammar on bars, alt text. Hand-written rows.
import assert from "node:assert/strict";
import { test } from "node:test";
import { pyramid } from "../src/pyramid.js";
import { document, marks, row, tokens } from "./rows.js";

const AGES = ["0-14", "15-64", "65+"];
const profile = (period, values, extra = {}) =>
  AGES.flatMap((age, i) => [
    row("EL", period, values[i], { sex: "male", age, ...extra }),
    row("EL", period, values[i] + 1, { sex: "female", age, ...extra }),
  ]);
const ROWS = [...profile("2001", [900, 3500, 1000]), ...profile("2024", [700, 3300, 1300], { status: "provisional" })];
const SPEC = { title: "Οι ηλικιωμένοι ξεπερνούν τα παιδιά", labels: { EL: "Ελλάδα" } };
const chart = (rows = ROWS, spec = SPEC) => pyramid(rows, spec, { tokens, document });

test("men to the left, women to the right, the latest year as bars", () => {
  const bars = marks(chart().figure, "bar");
  assert.equal(bars.length, 2, "main bars and the comparison outline");
  const [main, outline] = bars;
  const xs = [...main.querySelectorAll("rect")].map((r) => +r.getAttribute("x"));
  const centre = Math.min(...xs.filter((x, i) => i % 2 === 1));
  assert.ok(xs.some((x) => x < centre), "some bars extend left");
  // provisional: hollow bars in the accent
  assert.equal(main.getAttribute("fill"), tokens["color-background"]);
  assert.equal(main.getAttribute("stroke"), tokens["color-accent"]);
  assert.equal(outline.getAttribute("fill"), "none");
  assert.equal(outline.getAttribute("stroke"), tokens["color-comparator"]);
});

test("the oldest age is at the top", () => {
  const ys = (age) => {
    const ticks = [...chart().figure.querySelectorAll('g[data-mark="y-axis tick label"] text')];
    return +ticks.find((t) => t.textContent === age).getAttribute("transform").match(/,([-\d.]+)\)/)[1];
  };
  assert.ok(ys("65+") < ys("0-14"));
});

test("projected bars are lighter with a dashed edge", () => {
  const rows = profile("2050", [500, 3000, 1600], { nature: "projected" });
  const [main] = marks(chart(rows).figure, "bar");
  assert.equal(main.getAttribute("fill-opacity"), String(tokens["opacity-band-80"]));
  assert.equal(main.getAttribute("stroke-dasharray"), tokens["stroke-dash-projected"]);
});

test("alt text gives each profile's totals and largest group", () => {
  assert.equal(
    chart().alt,
    "Οι ηλικιωμένοι ξεπερνούν τα παιδιά. Ελλάδα 2024: άνδρες 5.300, γυναίκες 5.303, μεγαλύτερη ομάδα 15-64; " +
      "Ελλάδα 2001: άνδρες 5.400, γυναίκες 5.403, μεγαλύτερη ομάδα 15-64; προσωρινές τιμές: 2024.",
  );
});

test("the table shows sex and age", () => {
  const heads = [...chart().table.querySelectorAll("th")].map((th) => th.textContent);
  assert.deepEqual(heads.slice(0, 4), ["Περιοχή", "Περίοδος", "Φύλο", "Ηλικία"]);
});

test("a pyramid refuses totals, three profiles and a missing main year", () => {
  assert.throws(() => chart([row("EL", "2024", 1)]), /male and female/);
  assert.throws(() => chart([...ROWS, ...profile("1991", [1, 2, 3])]), /two profiles/);
  assert.throws(() => chart(ROWS, { ...SPEC, period: "1981" }), /no rows for EL in 1981/);
  assert.throws(() => chart(ROWS.map((r, i) => (i === 0 ? { ...r, value: null, status: "not_available" } : r))), /needs every age/);
});

test("the default year ignores scenarios; a numeric year works", () => {
  const scenario = profile("2050", [1, 2, 3], { nature: "scenario", scenario_id: "low" });
  assert.ok(chart([...profile("2024", [700, 3300, 1300]), ...scenario]).alt.includes("Ελλάδα 2024: άνδρες"));
  assert.ok(chart(ROWS, { ...SPEC, period: 2001 }).alt.includes("Ελλάδα 2001: άνδρες 5.400"));
});

test("alt text names a projected profile as a projection", () => {
  const rows = profile("2050", [500, 3000, 1600], { nature: "projected" });
  assert.ok(chart(rows).alt.includes("Ελλάδα 2050, προβολή: άνδρες"));
});
