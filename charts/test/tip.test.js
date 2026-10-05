// Every chart type gives each drawn value a tooltip (PROPOSAL §7A): value, unit, nature,
// status and source, all taken from the row. Runs over the gallery's illustrative rows.
import assert from "node:assert/strict";
import { test } from "node:test";
import { TEXT, tip } from "../src/chart.js";
import { CHARTS } from "../visual/gallery.js";
import { document, row, tokens } from "./rows.js";

const el = TEXT.el;

test("the tooltip names area, period, value with unit, nature, status, source and dataset", () => {
  const s = { label: (k) => ({ EL: "Ελλάδα", low: "χαμηλή" })[k] ?? k, format: (v) => String(v).replace(".", ","), unit: "άτομα", text: el };
  assert.equal(
    tip(s, row("EL", "2024", 1.5, { status: "provisional", nature: "scenario", scenario_id: "low" })),
    "Ελλάδα (χαμηλή) 2024: 1,5 άτομα · σενάριο, προσωρινή · eurostat, demo_gind",
  );
});

for (const [name, [type, rows, spec]] of Object.entries(CHARTS))
  test(`${name}: every tooltip comes from a row`, () => {
    const titles = [...type(rows, spec, { tokens, document }).figure.querySelectorAll("svg title")].map((t) => t.textContent);
    assert.ok(titles.length > 0, "no tooltips");
    const natures = Object.values(el.nature);
    const statuses = Object.values(el.status);
    for (const t of titles) {
      assert.ok(t.includes(`${rows[0].source}, ${rows[0].dataset_code}`), t);
      assert.ok(natures.some((n) => t.includes(n)) && statuses.some((x) => t.includes(x)), t);
    }
  });
