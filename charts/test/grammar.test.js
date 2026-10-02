// The epistemic grammar for every nature × status (PROPOSAL §7A), and its vocabulary
// against the provenance contract, which defines it.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { NATURES, STATUSES, style } from "../src/grammar.js";
import { TEXT } from "../src/chart.js";

const CONTRACT = readFileSync(new URL("../../pipeline/src/grpop/provenance.py", import.meta.url), "utf8");
const enumValues = (name) => {
  // The class body: the lines after its header up to the first unindented one.
  const body = CONTRACT.split(`class ${name}(StrEnum):`)[1].split(/\n(?=\S)/)[0];
  return [...body.matchAll(/^\s+[A-Z_0-9]+ = "([a-z_0-9]+)"/gm)].map((m) => m[1]).sort();
};

test("the grammar covers exactly the nature and status vocabularies of the contract", () => {
  assert.deepEqual([...NATURES].sort(), enumValues("Nature"));
  assert.deepEqual([...STATUSES].sort(), enumValues("Status"));
});

test("every locale labels every nature, status, sex and interval bound of the contract", () => {
  for (const [lang, t] of Object.entries(TEXT)) {
    assert.deepEqual(Object.keys(t.nature).sort(), [...NATURES].sort(), lang);
    assert.deepEqual(Object.keys(t.status).sort(), [...STATUSES].sort(), lang);
    assert.deepEqual(Object.keys(t.sex).sort(), enumValues("Sex"), lang);
    assert.deepEqual(Object.keys(t.interval).sort(), enumValues("Interval"), lang);
  }
});

test("Greek labels every unit of definitions.yaml, and only those", () => {
  const yaml = readFileSync(new URL("../../pipeline/src/grpop/definitions.yaml", import.meta.url), "utf8");
  const units = [...new Set([...yaml.matchAll(/^\s+unit:\s*(.+?)\s*$/gm)].map((m) => m[1].replace(/^["']|["']$/g, "")))];
  assert.deepEqual(Object.keys(TEXT.el.units).sort(), units.sort());
});

const LINE = {
  observed: { dash: null, band: false, color: null },
  official_estimate: { dash: null, band: false, color: null },
  derived: { dash: null, band: false, color: null },
  projected: { dash: "stroke-dash-projected", band: true, color: null },
  scenario: { dash: "stroke-dash-scenario", band: false, color: "color-scenario" },
};
const POINT = {
  final: { drawn: true, hollow: false },
  revised: { drawn: true, hollow: false },
  provisional: { drawn: true, hollow: true },
  not_available: { drawn: false, hollow: false },
};

for (const nature of NATURES)
  for (const status of STATUSES)
    test(`${nature} × ${status}`, () => {
      assert.deepEqual({ ...style(nature, status) }, { ...LINE[nature], ...POINT[status] });
      assert.ok(Object.isFrozen(style(nature, status)));
    });

test("an unknown nature or status throws", () => {
  assert.throws(() => style("forecast", "final"), /unknown nature/);
  assert.throws(() => style("observed", "estimated"), /unknown status/);
});
