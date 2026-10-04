// Pages made before each render (pre-render) from the data product, catalog.json and the
// pipeline's definitions and registry (ADR 0006: read where they live, never copied).
// The pages hold shortcodes, not values: every number is still read by fact() and chart()
// at render time. Generated files are not committed (.gitignore).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import yaml from "js-yaml";
import { load } from "./product.js";

const ROOT = new URL("../../", import.meta.url);
const read = (path) => readFileSync(new URL(path, ROOT), "utf8");
const front = (title) => `---\ntitle: "${title.replace(/"/g, '\\"')}"\n---\n\n{{< include /_tier.md >}}\n\n`;
const anchor = (definitionId) => definitionId.replace(/[^a-z0-9]+/g, "-");

/** The latest period with a central value for geo, sex and age, or undefined. */
export function latest(rows, geo, sex = "total", age = "total") {
  const periods = rows
    .filter((r) => r.geo_code === geo && r.sex === sex && r.age === age && !r.interval && !r.scenario_id && r.value !== null)
    .map((r) => r.period);
  return periods.sort().at(-1);
}

const fact = (name, geo, period, sex, age) => `{{< fact ${name} ${geo} ${period} ${sex} ${age} >}}`;

function indicator(dir, catalog, { name, title, sex = "total", age = "total" }) {
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
  const page =
    front(title) +
    `Η πιο πρόσφατη τιμή για την Ελλάδα είναι του ${period}:\n\n${facts.join("\n")}\n\n` +
    `{{< chart indicators/${name}.json >}}\n\n` +
    `Ορισμός: [${rows[0].definition_id}](/definitions.qmd#${anchor(rows[0].definition_id)}).\n`;
  return { page, spec };
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
    "[Όλοι οι δείκτες](indicators/index.qmd) · [Ορισμοί](definitions.qmd) · [Πηγές](sources.qmd)\n"
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
  const files = {};
  for (const item of catalog.indicators) {
    const { page, spec } = indicator(dir, catalog, item);
    files[`indicators/${item.name}.qmd`] = page;
    files[`indicators/${item.name}.json`] = JSON.stringify(spec, null, 1) + "\n";
  }
  files["indicators/index.qmd"] =
    front("Δείκτες") + catalog.indicators.map((i) => `- [${i.title}](${i.name}.qmd)`).join("\n") + "\n";
  files["index.qmd"] = home(dir, catalog);
  files["definitions.qmd"] = definitions(dir, catalog.indicators.map((i) => i.name));
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
