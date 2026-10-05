// Pages made from the data product, on a minimal product written here (hand-written rows,
// not data), and the link check on a hand-made _site.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { brokenLinks } from "../src/links.js";
import { latest, pages, TEXTS } from "../src/pages.js";

const HEADER =
  "metric,definition_id,geo_code,geo_vintage,period,sex,age,value,unit,source,dataset_code,source_url,vintage,retrieved_at,transform_version,nature,status,break_in_series,scenario_id,interval";
const row = (geo, period, value, scenario = "", nature = "official_estimate", interval = "") =>
  `population,population_1jan@v1,${geo},NUTS2024,${period},total,total,${value},persons,Eurostat,demo_pjan,https://example.org/x,2026-09-15,2026-10-02T00:00:00.000000+0000,1,${scenario ? "scenario" : nature},final,false,${scenario},${interval}`;
const DIR = mkdtempSync(join(tmpdir(), "kohortes-pages-"));
const MANIFEST = {};
const write = (file, text) => {
  writeFileSync(join(DIR, file), text);
  const name = file.replace(/\.[a-z]+$/, "");
  MANIFEST[name] = { files: { [file]: createHash("sha256").update(text).digest("hex") }, sources: [{ source_id: "eurostat_demo_pjan", sha256: "1" }] };
  writeFileSync(join(DIR, "manifest.json"), JSON.stringify(MANIFEST));
};
const csv = (...rows) => [HEADER, ...rows].join("\n") + "\n";
write("population.csv", csv(row("EL", "2023", "10.0"), row("EL", "2024", "11.0"), row("EL", "2030", "9.0", "s1"), row("EU27_2020", "2023", "450.0")));
write("population_regional.csv", csv(row("EL", "2024", "11.0"), row("EL30", "2024", "4.0"), row("EL30", "2023", "3.0")));
write("geometry_el_nuts2.geojson", JSON.stringify({ features: [{ properties: { geo_code: "EL30", name: "Αττική" } }, { properties: { geo_code: "EL43", name: "Κρήτη" } }] }));
write("projection.csv", csv(row("EL", "2025", "11.0", "", "projected"), row("EL", "2100", "8.0", "", "projected"), row("EL", "2100", "6.0", "s1")));
write("wpp.csv", csv(row("EL", "2024", "11.0", "", "projected"), row("EL", "2100", "7.0", "", "projected"), row("EL", "2100", "5.0", "", "projected", "95_lower")));
const CATALOG = {
  areas: { EL: "Ελλάδα", EU27_2020: "ΕΕ-27", EU27_2020_MEDIAN: "Διάμεσος ΕΕ-27" },
  home: ["population"],
  indicators: [{ name: "population", title: "Πληθυσμός" }],
  regions: { geometry: "geometry_el_nuts2", layout: "el_nuts2_tiles" },
  projections: { europop: "projection", wpp: "wpp", scenarios: { s1: "χαμηλότερη γονιμότητα" } },
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

test("every page explains itself in Greek: indicators, definitions, sources, AI use", () => {
  const files = pages(DIR, CATALOG);
  const page = files["indicators/population.qmd"];
  assert.ok(page.includes(TEXTS.indicators.population));
  assert.match(page, /<details class="kh-guide"><summary>Πώς διαβάζεται το γράφημα<\/summary>/);
  assert.match(page, /## Ορισμός\n\nΟ μόνιμος πληθυσμός[^\n]*\(\[Όλοι οι ορισμοί\]\(\/definitions\.qmd#population-1jan-v1\)\)/);
  assert.match(files["definitions.qmd"], /## Πληθυσμός την 1η Ιανουαρίου \{#population-1jan-v1\}\n\n`population_1jan@v1` · μονάδα: άτομα/);
  assert.match(files["sources.qmd"], /## Πληθυσμός την 1η Ιανουαρίου κατά ηλικία και φύλο/);
  assert.match(files["sources.qmd"], /Αναφορά: Source: Eurostat, dataset demo_pjan\n/); // the provider's credit line, filled in
  assert.doesNotMatch(files["ai.qmd"], /\*\*E[LN]\.\*\*|The code/);
  for (const name of ["index.qmd", "indicators/index.qmd", "regions/index.qmd", "regions/EL30.qmd", "projections.qmd"])
    assert.doesNotMatch(files[name], /data product|registry\]/, name);
});

test("texts.yaml explains every indicator of the catalog, and types no value", () => {
  const catalog = JSON.parse(readFileSync(new URL("../catalog.json", import.meta.url), "utf8"));
  assert.deepEqual(Object.keys(TEXTS.indicators).sort(), catalog.indicators.map((i) => i.name).sort());
  for (const [name, text] of [...Object.entries(TEXTS.pages), ...Object.entries(TEXTS.indicators)]) {
    assert.doesNotMatch(text, /\d[.,]\d|\b\d{4}\b/, name); // no decimals, no years: values come from the data
    assert.match(text, /[α-ω]/, name);
  }
  assert.throws(() => pages(DIR, { ...CATALOG, indicators: [{ name: "population_regional", title: "x" }] }), /no explanation/);
});

test("a region page compares the region with Greece, by its GISCO name; regions without data get no section", () => {
  const files = pages(DIR, CATALOG);
  const page = files["regions/EL30.qmd"];
  assert.match(page, /title: "Αττική"/);
  assert.match(page, /2024: \{\{< fact population_regional EL30 2024 total total >\}\}, Ελλάδα: \{\{< fact population_regional EL 2024/);
  assert.match(page, /\{\{< chart regions\/EL30-population\.json >\}\}/);
  const spec = JSON.parse(files["regions/EL30-population.json"]);
  // a count shows the region alone: beside the country's it would only show the country's scale
  assert.deepEqual([spec.focus, spec.geo, spec.labels.EL30], ["EL30", ["EL30"], "Αττική"]);
  assert.doesNotMatch(files["regions/EL43.qmd"], /fact/);
  assert.match(files["regions/index.qmd"], /\[Αττική\]\(EL30\.qmd\)\n- \[Κρήτη\]\(EL43\.qmd\)/);
});

test("a regional count gets proportional symbols; a regional rate a choropleth beside the tile grid", () => {
  const rate = (text) => text.replaceAll(",persons,", ",live births per woman,");
  write("total_fertility_rate.csv", rate(csv(row("EL", "2024", "1.3"))));
  write("total_fertility_rate_regional.csv", rate(csv(row("EL", "2024", "1.3"), row("EL30", "2024", "1.1"), row("EL43", "2024", "1.5"))));
  const files = pages(DIR, { ...CATALOG, indicators: [...CATALOG.indicators, { name: "total_fertility_rate", title: "Γονιμότητα" }] });
  const map = JSON.parse(files["indicators/population-map.json"]);
  assert.deepEqual([map.type, map.geo, map.period, map.focus, map.geometry], ["symbols", ["EL30", "EL43"], "2024", null, "geometry_el_nuts2"]);
  assert.equal(files["indicators/population-tiles.json"], undefined); // the regions would lie flat under the country's line
  assert.match(
    files["indicators/total_fertility_rate.qmd"],
    /## Περιφέρειες\n\n[^{]+\{\{< chart indicators\/total_fertility_rate-map\.json >\}\}\n\n\{\{< chart indicators\/total_fertility_rate-tiles\.json >\}\}/,
  );
  assert.equal(JSON.parse(files["indicators/total_fertility_rate-map.json"]).type, "choropleth");
  const tiles = JSON.parse(files["indicators/total_fertility_rate-tiles.json"]);
  assert.deepEqual([tiles.type, tiles.geo, tiles.focus, tiles.layout, tiles.labels.EL43], ["tiles", ["EL30", "EL43", "EL"], "EL", "el_nuts2_tiles", "Κρήτη"]);
});

test("the projections page quotes the baseline and the WPP median, and names every scenario", () => {
  const files = pages(DIR, CATALOG);
  const page = files["projections.qmd"];
  assert.match(page, /2025: \{\{< fact projection EL 2025 total total >\}\}· 2100: \{\{< fact projection EL 2100/);
  assert.match(page, /2024: \{\{< fact wpp EL 2024 total total >\}\}· 2100: \{\{< fact wpp EL 2100 total total >\}\}\.\n\nΟ ΟΗΕ δίνει/);
  assert.match(page, /\*\*όχι πρόβλεψη\*\*/);
  assert.equal(JSON.parse(files["projections/europop.json"]).labels.s1, "χαμηλότερη γονιμότητα");
  assert.throws(() => pages(DIR, { ...CATALOG, projections: { ...CATALOG.projections, scenarios: {} } }), /no Greek name for the scenarios s1/);
});

test("the mortality page quotes the probability of dying at each age and draws the death rates as a Lexis surface", () => {
  const at = (metric, age) =>
    row("EL", "2024", "0.003").replace("population,population_1jan@v1", `${metric},${metric}@v1`).replace(",total,total,", `,total,${age},`).replace(",persons,", ",probability,");
  write("q.csv", csv(at("probability_of_dying", "0"), at("probability_of_dying", "65")));
  write("m.csv", csv(at("age_specific_death_rate", "0"), at("age_specific_death_rate", "65")));
  const files = pages(DIR, { ...CATALOG, life_table: { rate: "m", probability: "q", ages: ["0", "65"] } });
  const page = files["indicators/mortality_by_age.qmd"];
  assert.match(page, /- 0 ετών: \{\{< fact q EL 2024 total 0 >\}\}\n- 65 ετών: \{\{< fact q EL 2024 total 65 >\}\}/);
  assert.ok(page.includes(TEXTS.pages.mortality_after));
  const spec = JSON.parse(files["indicators/mortality_by_age.json"]);
  assert.deepEqual([spec.type, spec.data, spec.geo, spec.ages, spec.classes], ["lexis", "m", ["EL"], "single", "quantile"]);
  assert.match(files["indicators/index.qmd"], /\[Θνησιμότητα κατά ηλικία\]\(mortality_by_age\.qmd\)/);
  assert.match(files["definitions.qmd"], /\{#probability-of-dying-v1\}/);
  assert.match(files["definitions.qmd"], /\{#age-specific-death-rate-v1\}/);
});

test("the link check finds a broken local link and ignores external ones", () => {
  const root = mkdtempSync(join(tmpdir(), "kohortes-site-"));
  mkdirSync(join(root, "indicators"));
  writeFileSync(join(root, "index.html"), '<a href="indicators/a.html#x">a</a><a href="https://x.org">x</a><a href="#top">t</a><a href="/ai.html">r</a>');
  writeFileSync(join(root, "indicators", "a.html"), '<a href="../missing.html">m</a><img src="data:image/png;base64,AA">');
  assert.deepEqual(brokenLinks(root).sort(), [join("indicators", "a.html") + ": ../missing.html", "index.html: /ai.html (absolute)"].sort());
});
