// The waterfall: parts that must add up to the total, floating bars, alt text, table.
// The rows are hand-written, not data.
import assert from "node:assert/strict";
import { test } from "node:test";
import { waterfall } from "../src/waterfall.js";
import { document, marks, row, tokens } from "./rows.js";

const part = (definition_id, value, extra = {}) => row("EL", "2025", value, { definition_id, ...extra });
const ROWS = [part("natural_change@v1", -55386), part("net_migration@v1", 49637, { status: "provisional" }), part("population_change@v1", -5749)];
const SPEC = {
  title: "Η μετανάστευση δεν αντισταθμίζει την υπεροχή των θανάτων",
  parts: ["natural_change@v1", "net_migration@v1"],
  total: "population_change@v1",
  labels: { EL: "Ελλάδα", "natural_change@v1": "Φυσική μεταβολή", "net_migration@v1": "Καθαρή μετανάστευση", "population_change@v1": "Μεταβολή" },
};
const chart = (rows = ROWS, spec = SPEC) => waterfall(rows, spec, { tokens, document });

test("parts float from where the last one ended; the total starts at zero", () => {
  const { figure } = chart();
  const ticks = [...figure.querySelectorAll('g[data-mark="x-axis tick label"] text')].map((t) => t.textContent);
  assert.deepEqual(ticks, ["Φυσική μεταβολή", "Καθαρή μετανάστευση", "Μεταβολή"]);
  const bars = marks(figure, "bar").map((g) => g.querySelector("rect"));
  assert.equal(bars.length, 3);
  const [nat, mig, total] = bars.map((r) => [+r.getAttribute("y"), +r.getAttribute("height")]);
  assert.ok(Math.abs(mig[0] + mig[1] - (nat[0] + nat[1])) < 1); // migration rises from natural change's end
  assert.ok(total[1] < nat[1]); // the total is the small remainder
});

test("a provisional part is hollow", () => {
  const [, mig] = marks(chart().figure, "bar");
  assert.equal(mig.getAttribute("fill") ?? mig.querySelector("rect").getAttribute("fill"), tokens["color-background"]);
});

test("alt text lists the parts and the total; the table names each measure", () => {
  const { alt, table } = chart();
  assert.equal(
    alt,
    "Η μετανάστευση δεν αντισταθμίζει την υπεροχή των θανάτων. Φυσική μεταβολή −55.386; Καθαρή μετανάστευση 49.637; " +
      "σύνολο: Μεταβολή −5.749 (Ελλάδα 2025); προσωρινές τιμές: 2025.",
  );
  const heads = [...table.querySelectorAll("th")].map((th) => th.textContent);
  assert.equal(heads[1], "Μέγεθος");
  assert.ok([...table.querySelectorAll("td")].some((td) => td.textContent === "Καθαρή μετανάστευση"));
});

test("it fails unless the parts add up to the total, within the tolerance", () => {
  const off = [...ROWS.slice(0, 2), part("population_change@v1", -5700)];
  assert.throws(() => chart(off), /the parts add up to -5749, the total population_change@v1 is -5700/);
  assert.doesNotThrow(() => chart(off, { ...SPEC, tolerance: 49 }));
});

test("it needs one area, one period, every part once and nothing else", () => {
  assert.throws(() => chart(ROWS.slice(1)), /natural_change@v1: needs exactly one value/);
  assert.throws(() => chart([...ROWS, part("births@v1", 1)]), /neither a part nor the total: births@v1/);
  assert.throws(() => chart([...ROWS, row("PT", "2025", 1, { definition_id: "natural_change@v1" })]), /one geo_code/);
  assert.throws(() => chart(ROWS, { ...SPEC, total: undefined }), /spec.parts and spec.total/);
});
