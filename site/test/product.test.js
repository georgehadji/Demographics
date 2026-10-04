// The gateway to the data product, on a minimal product written here (hand-written rows,
// not data; built at test time so line endings cannot change the hashes).
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { chart, fact, load, PROVENANCE } from "../src/product.js";

const HEADER =
  "metric,definition_id,geo_code,geo_vintage,period,sex,age,value,unit,source,dataset_code,source_url,vintage,retrieved_at,transform_version,nature,status,break_in_series,scenario_id,interval";
const row = (geo, period, value, nature, status, source = "Eurostat") =>
  `population,population_1jan@v1,${geo},NUTS2024,${period},total,total,${value},persons,${source},demo_pjan,https://example.org/demo_pjan,2026-09-15,2026-10-02T00:00:00.000000+0000,1,${nature},${status},false,,`;
const FILES = {
  population: [
    row("EL", "2022", "", "observed", "not_available"),
    row("EL", "2023", "10400000.0", "official_estimate", "final"),
    row("EL", "2024", "10390000.5", "official_estimate", "provisional"),
    row("EL", "2050", "9000000.0", "projected", "final"),
    row("PT", "2023", "10500000.0", "official_estimate", "final"),
  ],
  tampered: [row("EL", "2023", "1.0", "observed", "final")],
  unsourced: [row("EL", "2023", "1.0", "observed", "final", "")],
  unlisted: [row("EL", "2023", "1.0", "observed", "final")],
  rounded: [row("EL", "2023", "46.667", "derived", "final")],
};
// a derived indicator carries the official value's decimals in the manifest
const DECIMALS = { rounded: 1 };
const DIR = mkdtempSync(join(tmpdir(), "kohortes-"));
const manifest = {};
for (const [name, rows] of Object.entries(FILES)) {
  const text = [HEADER, ...rows].join("\n") + "\n";
  writeFileSync(join(DIR, `${name}.csv`), text);
  const sha = name === "tampered" ? "0".repeat(64) : createHash("sha256").update(text).digest("hex");
  if (name !== "unlisted") manifest[name] = { files: { [`${name}.csv`]: sha }, decimals: DECIMALS[name] };
}
writeFileSync(join(DIR, "manifest.json"), JSON.stringify(manifest));

test("a fact is the formatted value with its source", () => {
  assert.equal(fact(DIR, "population", "EL", "2023"), '<span class="fact" title="Πηγή: Eurostat · demo_pjan · έκδοση 2026-09-15">10.400.000</span>');
});

test("a derived value is shown to the decimals the manifest gives", () => {
  assert.match(fact(DIR, "rounded", "EL", "2023"), />46,7</);
});

test("a provisional or projected fact says so in the text", () => {
  assert.match(fact(DIR, "population", "EL", "2024"), />10.390.000,5 \(προσωρινή\)</);
  assert.match(fact(DIR, "population", "EL", "2050"), />9.000.000 \(προβολή\)</);
});

test("a missing or unavailable value stops the render", () => {
  assert.throws(() => fact(DIR, "population", "EL", "1800"), /0 values in the data product/);
  assert.throws(() => fact(DIR, "population", "EL", "2023", "female"), /0 values/);
  assert.throws(() => fact(DIR, "population", "EL", "2022"), /not_available/);
});

test("a value without provenance stops the render", () => {
  assert.throws(() => load(DIR, "unlisted"), /not in the data product manifest/);
  assert.throws(() => load(DIR, "tampered"), /sha256 differs/);
  assert.throws(() => load(DIR, "unsourced"), /no source/);
  assert.throws(() => load(undefined, "population"), /KOHORTES_DATA/);
});

test("the provenance fields are fields of the contract", () => {
  const contract = readFileSync(new URL("../../pipeline/src/grpop/provenance.py", import.meta.url), "utf8");
  for (const f of PROVENANCE) assert.match(contract, new RegExp(`^    ${f}: `, "m"), f);
});

test("a chart gives the figure in both modes, its table and its CSV", () => {
  const html = chart(DIR, { type: "line", data: "population", geo: ["EL", "PT"], title: "Τίτλος", labels: { EL: "Ελλάδα" } });
  assert.equal(html.match(/<figure/g).length, 2);
  assert.match(html, /class="kh-light"/);
  assert.match(html, /class="kh-dark"/);
  assert.match(html, /<details><summary>Πίνακας δεδομένων<\/summary><table>/);
  assert.match(html, /download="population.csv" href="data:text\/csv/);
  assert.throws(() => chart(DIR, { type: "pie", data: "population", geo: ["EL"], title: "x" }), /the site draws line/);
  assert.throws(() => chart(DIR, { type: "tiles", data: "population", geo: ["EL"], layout: "../x", title: "x" }), /not a reference table name/);
});
