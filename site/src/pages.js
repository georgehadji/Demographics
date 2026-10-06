// Pages made before each render (pre-render) from the data product, catalog.json and the
// pipeline's definitions and registry (ADR 0006: read where they live, never copied).
// The pages hold shortcodes, not values: every number is still read by fact() and chart()
// at render time. Generated files are not committed (.gitignore).
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import yaml from "js-yaml";
import { TEXT } from "../../charts/src/chart.js";
import { geometry, load } from "./product.js";
import { DEFINITIONS, REGISTRY } from "./repo.js";

const ROOT = new URL("../../", import.meta.url);
const read = (path) => readFileSync(new URL(path, ROOT), "utf8");
const front = (title) => `---\ntitle: "${title.replace(/"/g, '\\"')}"\n---\n\n{{< include /_tier.md >}}\n\n`;
const anchor = (definitionId) => definitionId.replace(/[^a-z0-9]+/g, "-");
/** The explanatory text of the pages (texts.yaml). */
export const TEXTS = yaml.load(read("site/texts.yaml"));
const DEFS = Object.fromEntries(yaml.load(read("pipeline/src/grpop/definitions.yaml")).map((d) => [d.id, d]));
// a native <details>: Quarto's collapsible callout puts aria-expanded on a div, which axe rejects
const collapsed = (title, body) => `<details class="kh-guide"><summary>${title}</summary>\n\n${body}\n</details>\n\n`;
const list = new Intl.ListFormat("el", { type: "conjunction" });

/** A chart with its explanation in plain words above it (texts.yaml charts.<kind>). */
function explained(kind, path, vars = {}, after = "") {
  if (!TEXTS.charts[kind]) throw new Error(`texts.yaml: no explanation of the chart ${kind}`);
  const text = TEXTS.charts[kind].replace(/\{(\w+)\}/g, (_, k) => {
    if (vars[k] === undefined) throw new Error(`texts.yaml charts.${kind}: nothing fills {${k}}`);
    return vars[k];
  });
  return `::: {.callout-note title="Τι δείχνει το διάγραμμα"}\n${text}${after}:::\n\n{{< chart ${path} >}}\n`;
}

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
 * The regions of an indicator that has a regional series. A rate: a choropleth of the
 * latest period beside the tile grid over time, which shows every region at the same
 * size, as PROPOSAL §7A asks of a choropleth. A count: proportional symbols only; on
 * tiles beside the country's line the regions would lie flat at the bottom.
 */
function regional(dir, catalog, { name, title, sex = "total", age = "total" }, names) {
  const data = `${name}_regional`;
  const rows = load(dir, data);
  const period = latest(rows, "EL", sex, age);
  if (!period) return { text: "", files: {} };
  const codes = Object.keys(names);
  const common = { data, sex, age, labels: { EL: catalog.areas.EL, ...names } };
  const count = rows[0].unit === "persons";
  const files = {
    [`indicators/${name}-map.json`]: json({
      type: count ? "symbols" : "choropleth",
      ...common,
      geo: codes,
      period,
      focus: null,
      geometry: catalog.regions.geometry,
      title: `${title}: Περιφέρειες, ${period}`,
    }),
  };
  if (!count)
    files[`indicators/${name}-tiles.json`] = json({
      type: "tiles",
      ...common,
      geo: [...codes, "EL"],
      focus: "EL",
      layout: catalog.regions.layout,
      title: `${title}: Περιφέρειες και ${catalog.areas.EL}`,
    });
  const charts = Object.entries(files).map(([path, spec]) => explained(JSON.parse(spec).type, path, { indicator: title }));
  return {
    text: `## Περιφέρειες\n\n${TEXTS.pages.regional}\n${charts.join("\n")}\n[Η σελίδα κάθε Περιφέρειας](../regions/index.qmd)\n`,
    files,
  };
}

/** An indicator's page and chart specs; `names` maps each region's code to its name. */
function indicator(dir, catalog, manifest, names, item) {
  const { name, title, sex = "total", age = "total" } = item;
  const rows = load(dir, name);
  const period = latest(rows, "EL", sex, age);
  if (!period) throw new Error(`${name}: no value for Greece (sex ${sex}, age ${age})`);
  const areas = Object.keys(catalog.areas).filter((g) => latest(rows, g, sex, age));
  // a count beside the EU's would only show the EU's scale; its value stays in the facts
  const count = rows[0].unit === "persons";
  const drawn = count ? ["EL"] : areas;
  const facts = areas
    .filter((g) => latest(rows, g, sex, age) === period)
    .map((g) => `- ${catalog.areas[g]}: ${fact(name, g, period, sex, age)}`);
  const spec = {
    type: "line",
    data: name,
    geo: drawn,
    sex,
    age,
    focus: "EL",
    title: `${title}: ${drawn.map((g) => catalog.areas[g]).join(", ")}`,
    labels: Object.fromEntries(drawn.map((g) => [g, catalog.areas[g]])),
  };
  const text = TEXTS.indicators[name];
  if (!text) throw new Error(`texts.yaml: no explanation of the indicator ${name}`);
  const def = DEFS[rows[0].definition_id];
  const regions = manifest[`${name}_regional`] ? regional(dir, catalog, item, names) : { text: "", files: {} };
  const page =
    front(title) +
    `Η πιο πρόσφατη τιμή για την Ελλάδα είναι του ${period}:\n\n${facts.join("\n")}\n\n` +
    explained(
      count ? "line_alone" : "line",
      `indicators/${name}.json`,
      { indicator: title, areas: list.format(drawn.map((g) => catalog.areas[g])) },
      drawn.filter((g) => TEXTS.areas[g]).map((g) => `\n${TEXTS.areas[g]}`).join(""),
    ) +
    "\n" +
    collapsed("Πώς διαβάζεται το γράφημα", TEXTS.pages.chart) +
    `${text}\n` +
    `## Ορισμός\n\n${def.el.description} ([Όλοι οι ορισμοί](/definitions.qmd#${anchor(def.id)}))\n\n` +
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
    const alone = rows[0].unit === "persons";
    const geos = alone ? [geo] : [geo, "EL"];
    const labels = { [geo]: name, EL: catalog.areas.EL };
    files[path] = json({ type: "line", data, geo: geos, sex, age, focus: geo, title: `${title}: ${geos.map((g) => labels[g]).join(", ")}`, labels });
    parts.push(
      `## ${title}\n\n${period}: ${fact(data, geo, period, sex, age)}${el}. ` +
        `[Όλες οι χώρες](../indicators/${n}.qmd)\n\n` +
        explained(alone ? "region_alone" : "region", path, { indicator: title, region: name }),
    );
  }
  files[`regions/${geo}.qmd`] = front(name) + `Κωδικός NUTS 2: \`${geo}\`.\n\n${TEXTS.pages.region}\n` + parts.join("\n");
  return files;
}

function regions(dir, catalog, manifest, features) {
  const sorted = [...features].sort((a, b) => a.name.localeCompare(b.name, "el"));
  return Object.assign(
    { "regions/index.qmd": front("Περιφέρειες") + `${TEXTS.pages.regions}\n` + sorted.map((p) => `- [${p.name}](${p.geo_code}.qmd)`).join("\n") + "\n" },
    ...features.map((p) => region(dir, catalog, manifest, p)),
  );
}

/** Mortality by age for Greece: the probability of dying at a few ages, and the Lexis
 * surface of the death rates by age and year (Eurostat life table). */
function mortality(dir, catalog) {
  const { rate, probability, ages } = catalog.life_table;
  const q = load(dir, probability);
  const period = latest(q, "EL", "total", ages[0]);
  if (!period) throw new Error(`${probability}: no value for Greece at age ${ages[0]}`);
  const defs = [rate, probability].map((name) => DEFS[load(dir, name)[0].definition_id]);
  const facts = ages.map((a) => `- ${a} ετών: ${fact(probability, "EL", period, "total", a)}`);
  const EL = catalog.areas.EL;
  return {
    "indicators/mortality_by_age.json": json({
      type: "lexis",
      data: rate,
      geo: ["EL"],
      sex: "total",
      ages: "single",
      classes: "quantile",
      focus: "EL",
      title: `${defs[0].el.title}: ${EL}, κατά ηλικία και έτος`,
      labels: { EL },
    }),
    "indicators/mortality_by_age.qmd":
      front("Θνησιμότητα κατά ηλικία") +
      `${TEXTS.pages.mortality}\n` +
      `## Πιθανότητα θανάτου μέσα στον επόμενο χρόνο, ${EL}, ${period}\n\n${facts.join("\n")}\n\n` +
      explained("lexis", "indicators/mortality_by_age.json") +
      "\n" +
      TEXTS.pages.mortality_after +
      "\n## Ορισμοί\n\n" +
      defs.map((d) => `- **${d.el.title}:** ${d.el.description} ([ορισμός](/definitions.qmd#${anchor(d.id)}))`).join("\n") +
      "\n",
  };
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
      `${TEXTS.pages.projections}\n` +
      `## Eurostat EUROPOP2025\n\nΒασική προβολή για ${EL}, ${span(europop, rows)}.\n\n` +
      `${TEXTS.pages.projections_europop}\n` +
      explained("europop", "projections/europop.json") +
      "\n" +
      `## ΟΗΕ, Παγκόσμιες Πληθυσμιακές Προοπτικές 2024\n\nΔιάμεσος για ${EL}, ${span(wpp, load(dir, wpp))}.\n\n` +
      `${TEXTS.pages.projections_wpp}\n` +
      "Ο πληθυσμός εδώ είναι της 1ης Ιουλίου και δεν συγκρίνεται τιμή προς τιμή με της 1ης Ιανουαρίου " +
      "([ορισμός](definitions.qmd#population-1jul-v1)).\n\n" +
      explained("wpp", "projections/wpp.json"),
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
    `${TEXTS.pages.home}\n` +
    `${lines.join("\n")}\n\n` +
    TEXTS.pages.home_after
  );
}

function definitions(dir, names) {
  const used = new Set(names.map((n) => load(dir, n)[0]?.definition_id));
  const items = Object.values(DEFS)
    .filter((d) => used.has(d.id))
    .map((d) => `## ${d.el.title} {#${anchor(d.id)}}\n\n\`${d.id}\` · μονάδα: ${TEXT.el.units[d.unit]}\n\n${d.el.description}\n`);
  return front("Ορισμοί") + `${TEXTS.pages.definitions.replace("{definitions}", DEFINITIONS)}\n` + items.join("\n");
}

function sources(manifest) {
  const registry = yaml.load(read("pipeline/src/grpop/sources/registry.yaml"));
  const used = new Set(Object.values(manifest).flatMap((e) => e.sources.map((s) => s.source_id)));
  const items = registry.sources
    .filter((s) => used.has(s.id))
    .map((s) => {
      const l = registry.licences[s.licence];
      const credit = l.attribution.replace("{dataset_code}", s.dataset_code);
      return `## ${s.title_el}\n\n- ${s.provider}, \`${s.dataset_code}\`\n- Άδεια: [${l.name}](${l.terms_url})\n- Αναφορά: ${credit}\n`;
    });
  return front("Πηγές") + `${TEXTS.pages.sources.replace("{registry}", REGISTRY)}\n` + items.join("\n");
}

/** The Greek part of AI_USE.md, between its EL and EN paragraphs. */
const greekAiUse = () => {
  const text = read("AI_USE.md");
  const [start, end] = [text.indexOf("**EL.** "), text.indexOf("**EN.**")];
  if (start < 0 || end < start) throw new Error("AI_USE.md: no EL part before the EN part");
  return text.slice(start + "**EL.** ".length, end);
};

/** Every generated file, path relative to site/ -> content. */
export function pages(dir, catalog = JSON.parse(readFileSync(new URL("../catalog.json", import.meta.url), "utf8"))) {
  const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  const features = geometry(dir, catalog.regions.geometry).features.map((f) => f.properties);
  const names = Object.fromEntries(features.map((p) => [p.geo_code, p.name]));
  const files = Object.assign({}, ...catalog.indicators.map((item) => indicator(dir, catalog, manifest, names, item)));
  files["indicators/index.qmd"] =
    front("Δείκτες") +
    `${TEXTS.pages.indicators}\n` +
    catalog.indicators.map((i) => `- [${i.title}](${i.name}.qmd)`).join("\n") +
    (catalog.life_table ? "\n- [Θνησιμότητα κατά ηλικία](mortality_by_age.qmd)" : "") +
    "\n";
  Object.assign(files, regions(dir, catalog, manifest, features), projections(dir, catalog));
  if (catalog.life_table) Object.assign(files, mortality(dir, catalog));
  files["index.qmd"] = home(dir, catalog);
  const { europop, wpp } = catalog.projections;
  const lifeTable = catalog.life_table ? [catalog.life_table.rate, catalog.life_table.probability] : [];
  files["definitions.qmd"] = definitions(dir, [...catalog.indicators.map((i) => i.name), europop, wpp, ...lifeTable]);
  files["sources.qmd"] = sources(manifest);
  files["ai.qmd"] = front("Χρήση τεχνητής νοημοσύνης") + greekAiUse();
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
