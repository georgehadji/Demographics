// Pages made from the data product, on a minimal product written here (hand-written rows,
// not data), and the link check on a hand-made _site.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { brokenLinks } from "../src/links.js";
import { latest, pages } from "../src/pages.js";

const HEADER =
  "metric,definition_id,geo_code,geo_vintage,period,sex,age,value,unit,source,dataset_code,source_url,vintage,retrieved_at,transform_version,nature,status,break_in_series,scenario_id,interval";
const row = (geo, period, value, scenario = "") =>
  `population,population_1jan@v1,${geo},NUTS2024,${period},total,total,${value},persons,Eurostat,demo_pjan,https://example.org/x,2026-09-15,2026-10-02T00:00:00.000000+0000,1,${scenario ? "scenario" : "official_estimate"},final,false,${scenario},`;
const DIR = mkdtempSync(join(tmpdir(), "kohortes-pages-"));
const text = [HEADER, row("EL", "2023", "10.0"), row("EL", "2024", "11.0"), row("EL", "2030", "9.0", "s1"), row("EU27_2020", "2023", "450.0")].join("\n") + "\n";
writeFileSync(join(DIR, "population.csv"), text);
const sha = createHash("sha256").update(text).digest("hex");
writeFileSync(
  join(DIR, "manifest.json"),
  JSON.stringify({ population: { files: { "population.csv": sha }, sources: [{ source_id: "eurostat_demo_pjan", sha256: "1" }] } }),
);
const CATALOG = {
  areas: { EL: "Ελλάδα", EU27_2020: "ΕΕ-27", EU27_2020_MEDIAN: "Διάμεσος ΕΕ-27" },
  home: ["population"],
  indicators: [{ name: "population", title: "Πληθυσμός" }],
};

test("the latest period ignores scenarios and missing values", () => {
  const rows = [
    { geo_code: "EL", period: "2024", sex: "total", age: "total", value: 1 },
    { geo_code: "EL", period: "2030", sex: "total", age: "total", value: 1, scenario_id: "s1" },
    { geo_code: "EL", period: "2025", sex: "total", age: "total", value: null },
  ];
  assert.equal(latest(rows, "EL"), "2024");
  assert.equal(latest(rows, "PT"), undefined);
});

test("an indicator page quotes its values through fact() and compares only areas with data", () => {
  const files = pages(DIR, CATALOG);
  const page = files["indicators/population.qmd"];
  assert.match(page, /του 2024:/);
  assert.match(page, /\{\{< fact population EL 2024 total total >\}\}/);
  assert.doesNotMatch(page, /fact population EU27_2020 2024/); // its latest year is 2023
  assert.doesNotMatch(page, /\d{2}\.\d/); // no value typed into the page
  const spec = JSON.parse(files["indicators/population.json"]);
  assert.deepEqual(spec.geo, ["EL", "EU27_2020"]);
  assert.match(files["index.qmd"], /\{\{< fact population EL 2024 total total >\}\}/);
  assert.match(files["definitions.qmd"], /\{#population-1jan-v1\}/);
  assert.match(files["sources.qmd"], /demo_pjan/);
  assert.doesNotMatch(files["sources.qmd"], /demo_find/); // only the sources the product reads
});

test("the link check finds a broken local link and ignores external ones", () => {
  const root = mkdtempSync(join(tmpdir(), "kohortes-site-"));
  mkdirSync(join(root, "indicators"));
  writeFileSync(join(root, "index.html"), '<a href="indicators/a.html#x">a</a><a href="https://x.org">x</a><a href="#top">t</a><a href="/ai.html">r</a>');
  writeFileSync(join(root, "indicators", "a.html"), '<a href="../missing.html">m</a><img src="data:image/png;base64,AA">');
  assert.deepEqual(brokenLinks(root).sort(), [join("indicators", "a.html") + ": ../missing.html", "index.html: /ai.html (absolute)"].sort());
});
