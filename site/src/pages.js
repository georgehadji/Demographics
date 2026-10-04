// Pages made before each render (pre-render) from the data product, catalog.json and the
// pipeline's definitions and registry (ADR 0006: read where they live, never copied).
// The pages hold shortcodes, not values: every number is still read by fact() and chart()
// at render time. Generated files are not committed (.gitignore).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import yaml from "js-yaml";
import { geometry, load } from "./product.js";

const ROOT = new URL("../../", import.meta.url);
const read = (path) => readFileSync(new URL(path, ROOT), "utf8");
const front = (title) => `---\ntitle: "${title.replace(/"/g, '\\"')}"\n---\n\n{{< include /_tier.md >}}\n\n`;
const anchor = (definitionId) => definitionId.replace(/[^a-z0-9]+/g, "-");

/** The periods with a central value for geo, sex and age, sorted. */
const periods = (rows, geo, sex = "total", age = "total") =>
  rows
    .filter((r) => r.geo_code === geo && r.sex === sex && r.age === age && !r.interval && !r.scenario_id && r.value !== null)
    .map((r) => r.period)
    .sort();

/** The latest period with a central value for geo, sex and age, or undefined. */
export const latest = (rows, geo, sex, age) => periods(rows, geo, sex, age).at(-1);
const json = (spec) => JSON.stringify(spec, null, 1) + "\n";

const fact = (name, geo, period, sex, age) => `{{< fact ${name} ${geo} ${period} ${sex} ${age} >}}`;

/**
 * The regions of an indicator that has a regional series: a map at the latest period
 * (a choropleth for a rate, proportional symbols for a count) beside the tile grid over
 * time, which shows every region at the same size, as PROPOSAL §7A asks of a map.
 */
function regional(dir, catalog, { name, title, sex = "total", age = "total" }, names) {
  const data = `${name}_regional`;
  const rows = load(dir, data);
  const period = latest(rows, "EL", sex, age);
  if (!period) return { text: "", files: {} };
  const codes = Object.keys(names);
  const common = { data, sex, age, labels: { EL: catalog.areas.EL, ...names } };
  return {
    text:
      `## Περιφέρειες\n\n{{< chart indicators/${name}-map.json >}}\n\n{{< chart indicators/${name}-tiles.json >}}\n\n` +
      "[Η σελίδα κάθε Περιφέρειας](../regions/index.qmd)\n",
    files: {
      [`indicators/${name}-map.json`]: json({
        type: rows[0].unit === "persons" ? "symbols" : "choropleth",
        ...common,
        geo: codes,
        period,
        focus: null,
        geometry: catalog.regions.geometry,
        title: `${title}: Περιφέρειες, ${period}`,
      }),
      [`indicators/${name}-tiles.json`]: json({
        type: "tiles",
        ...common,
        geo: [...codes, "EL"],
        focus: "EL",
        layout: catalog.regions.layout,
        title: `${title}: Περιφέρειες και ${catalog.areas.EL}`,
      }),
    },
  };
}

/** An indicator's page and chart specs; `names` maps each region's code to its name. */
function indicator(dir, catalog, manifest, names, item) {
  const { name, title, sex = "total", age = "total" } = item;
  const rows = load(dir, name);
  const period = latest(rows, "EL", sex, age);
  if (!period) throw new Error(`${name}: no value for Greece (sex ${sex}, age ${age})`);
  const areas = Object.keys(catalog.areas).filter((g) => latest(rows, g, sex, age));
  const facts = areas
    .filter((g) => latest(rows, g, sex, age) === period)
    .map((g) => `- ${catalog.areas[g]}: ${fact(name, g, period, sex, age)}`);
  const spec = {
    type: "line",
    data: name,
    geo: areas,
    sex,
    age,
    focus: "EL",
    title: `${title}: ${areas.map((g) => catalog.areas[g]).join(", ")}`,
    labels: Object.fromEntries(areas.map((g) => [g, catalog.areas[g]])),
  };
  const regions = manifest[`${name}_regional`] ? regional(dir, catalog, item, names) : { text: "", files: {} };
  const page =
    front(title) +
    `Η πιο πρόσφατη τιμή για την Ελλάδα είναι του ${period}:\n\n${facts.join("\n")}\n\n` +
    `{{< chart indicators/${name}.json >}}\n\n` +
    `Ορισμός: [${rows[0].definition_id}](/definitions.qmd#${anchor(rows[0].definition_id)}).\n\n` +
    regions.text;
  return { [`indicators/${name}.qmd`]: page, [`indicators/${name}.json`]: json(spec), ...regions.files };
}

/** One region's page: each indicator with a regional series, the region against Greece. */
function region(dir, catalog, manifest, { geo_code: geo, name }) {
  const files = {};
  const parts = [];
  for (const { name: n, title, sex = "total", age = "total" } of catalog.indicators) {
    const data = `${n}_regional`;
    if (!manifest[data]) continue;
    const rows = load(dir, data);
    const period = latest(rows, geo, sex, age);
    if (!period) continue;
    const el = latest(rows, "EL", sex, age) === period ? `, ${catalog.areas.EL}: ${fact(data, "EL", period, sex, age)}` : "";
    const path = `regions/${geo}-${n}.json`;
    // a count beside the country's would only show the country's scale
    const geos = rows[0].unit === "persons" ? [geo] : [geo, "EL"];
    const labels = { [geo]: name, EL: catalog.areas.EL };
    files[path] = json({ type: "line", data, geo: geos, sex, age, focus: geo, title: `${title}: ${geos.map((g) => labels[g]).join(", ")}`, labels });
    parts.push(
      `## ${title}\n\n${period}: ${fact(data, geo, period, sex, age)}${el}. ` +
        `[Όλες οι χώρες](../indicators/${n}.qmd)\n\n{{< chart ${path} >}}\n`,
    );
  }
  files[`regions/${geo}.qmd`] = front(name) + `Η Περιφέρεια (NUTS 2: \`${geo}\`), με τους ρυθμούς και τους δείκτες σε σύγκριση με το σύνολο της χώρας.\n\n` + parts.join("\n");
  return files;
}

function regions(dir, catalog, manifest, features) {
  const sorted = [...features].sort((a, b) => a.name.localeCompare(b.name, "el"));
  return Object.assign(
    { "regions/index.qmd": front("Περιφέρειες") + sorted.map((p) => `- [${p.name}](${p.geo_code}.qmd)`).join("\n") + "\n" },
    ...features.map((p) => region(dir, catalog, manifest, p)),
  );
}

/** EUROPOP2025 with its sensitivity tests, and the UN WPP 2024 fan, for Greece. */
function projections(dir, catalog) {
  const { europop, wpp, scenarios } = catalog.projections;
  const rows = load(dir, europop);
  const unnamed = [...new Set(rows.map((r) => r.scenario_id).filter((id) => id && !scenarios[id]))];
  if (unnamed.length) throw new Error(`catalog.json: no Greek name for the scenarios ${unnamed.join(", ")}`);
  const span = (name, data) => {
    const p = periods(data, "EL");
    return `${p[0]}: ${fact(name, "EL", p[0], "total", "total")}· ${p.at(-1)}: ${fact(name, "EL", p.at(-1), "total", "total")}`;
  };
  const EL = catalog.areas.EL;
  return {
    "projections/europop.json": json({
      type: "line",
      data: europop,
      geo: ["EL"],
      age: "total",
      title: `Πληθυσμός: ${EL}, EUROPOP2025, βασική προβολή και σενάρια`,
      labels: { EL, ...scenarios },
    }),
    "projections/wpp.json": json({
      type: "line",
      data: wpp,
      geo: ["EL"],
      age: "total",
      title: `Πληθυσμός: ${EL}, UN WPP 2024, διάμεσος με διαστήματα 80% και 95%`,
      labels: { EL },
    }),
    "projections.qmd":
      front("Προβολές πληθυσμού") +
      "Οι προβολές δείχνουν τι συνεπάγονται υποθέσεις για τη γονιμότητα, τη θνησιμότητα και τη μετανάστευση. Δεν είναι προβλέψεις.\n\n" +
      `## Eurostat EUROPOP2025\n\nΒασική προβολή για ${EL}, ${span(europop, rows)}.\n\n` +
      "Τα σενάρια είναι οι έλεγχοι ευαισθησίας της Eurostat: μαθηματικές συνέπειες άλλων υποθέσεων, όχι προβλέψεις ούτε αποτελέσματα πολιτικών.\n\n" +
      "{{< chart projections/europop.json >}}\n\n" +
      `## ΟΗΕ, World Population Prospects 2024\n\nΔιάμεσος για ${EL}, ${span(wpp, load(dir, wpp))}.` +
      " Οι ζώνες είναι τα διαστήματα 80% και 95% της πιθανοτικής προβολής του ΟΗΕ. " +
      "Ο πληθυσμός εδώ είναι της 1ης Ιουλίου και δεν συγκρίνεται τιμή προς τιμή με της 1ης Ιανουαρίου " +
      "([ορισμός](definitions.qmd#population-1jul-v1)).\n\n" +
      "{{< chart projections/wpp.json >}}\n",
  };
}

function home(dir, catalog) {
  const byName = Object.fromEntries(catalog.indicators.map((i) => [i.name, i]));
  const lines = catalog.home.map((name) => {
    const period = latest(load(dir, name), "EL");
    return `- [${byName[name].title}](indicators/${name}.qmd), ${period}: ${fact(name, "EL", period, "total", "total")}`;
  });
  return (
    front("Κοόρτες: η δημογραφία της Ελλάδας") +
    "Ανοιχτό παρατηρητήριο: κάθε αριθμός διαβάζεται από τα επίσημα δεδομένα τη στιγμή που χτίζεται η σελίδα, μαζί με την πηγή του.\n\n" +
    `${lines.join("\n")}\n\n` +
    "Η καθαρή μετανάστευση είναι **εκτίμηση** της Eurostat, όχι μέτρηση.\n\n" +
    "[Όλοι οι δείκτες](indicators/index.qmd) · [Περιφέρειες](regions/index.qmd) · [Προβολές](projections.qmd) · " +
    "[Ορισμοί](definitions.qmd) · [Πηγές](sources.qmd)\n"
  );
}

function definitions(dir, names) {
  const used = new Set(names.map((n) => load(dir, n)[0]?.definition_id));
  const all = yaml.load(read("pipeline/src/grpop/definitions.yaml"));
  const items = all
    .filter((d) => used.has(d.id))
    .map((d) => `## ${d.title} {#${anchor(d.id)}}\n\n\`${d.id}\` · μονάδα: ${d.unit}\n\n${d.description}\n`);
  return (
    front("Ορισμοί") +
    "Οι ορισμοί των δεικτών, όπως τους διαβάζει ο κώδικας ([`definitions.yaml`](https://github.com/georgehadji/Demographics/blob/main/pipeline/src/grpop/definitions.yaml)). Οι περιγραφές είναι προς το παρόν στα αγγλικά.\n\n" +
    items.join("\n")
  );
}

function sources(manifest) {
  const registry = yaml.load(read("pipeline/src/grpop/sources/registry.yaml"));
  const used = new Set(Object.values(manifest).flatMap((e) => e.sources.map((s) => s.source_id)));
  const items = registry.sources
    .filter((s) => used.has(s.id))
    .map((s) => {
      const l = registry.licences[s.licence];
      return `## ${s.title}\n\n- ${s.provider}, \`${s.dataset_code}\`\n- Άδεια: [${l.name}](${l.terms_url})\n- Αναφορά: ${l.attribution}\n`;
    });
  return (
    front("Πηγές") +
    "Οι πηγές από τις οποίες χτίζεται το data product, με την άδεια και την αναφορά που ζητά η καθεμία ([registry](https://github.com/georgehadji/Demographics/blob/main/pipeline/src/grpop/sources/registry.yaml)).\n\n" +
    items.join("\n")
  );
}

/** Every generated file, path relative to site/ -> content. */
export function pages(dir, catalog = JSON.parse(readFileSync(new URL("../catalog.json", import.meta.url), "utf8"))) {
  const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  const features = geometry(dir, catalog.regions.geometry).features.map((f) => f.properties);
  const names = Object.fromEntries(features.map((p) => [p.geo_code, p.name]));
  const files = Object.assign({}, ...catalog.indicators.map((item) => indicator(dir, catalog, manifest, names, item)));
  files["indicators/index.qmd"] =
    front("Δείκτες") + catalog.indicators.map((i) => `- [${i.title}](${i.name}.qmd)`).join("\n") + "\n";
  Object.assign(files, regions(dir, catalog, manifest, features), projections(dir, catalog));
  files["index.qmd"] = home(dir, catalog);
  const { europop, wpp } = catalog.projections;
  files["definitions.qmd"] = definitions(dir, [...catalog.indicators.map((i) => i.name), europop, wpp]);
  files["sources.qmd"] = sources(manifest);
  files["ai.qmd"] = front("Χρήση τεχνητής νοημοσύνης") + read("AI_USE.md").replace(/^# .*\n/, "");
  return files;
}

export function writePages(dir) {
  const site = new URL("../", import.meta.url);
  for (const [path, text] of Object.entries(pages(dir))) {
    const url = new URL(path, site);
    mkdirSync(new URL("./", url), { recursive: true });
    writeFileSync(url, text);
  }
}
