// The site's only door to the data product (ADR 0005, layer L6: read, never compute).
// Values and chart rows come from files that grpop-build listed in manifest.json, checked
// against their sha256; every value must carry its provenance. Anything missing throws,
// and the shortcodes in kohortes.lua turn that into a failed render.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { csvParse } from "d3-dsv";
import { JSDOM } from "jsdom";
import { hexTokens } from "../../design/src/build.js";
import { formatNumber } from "../../design/src/format.js";
import { TEXT, vintageDate } from "../../charts/src/chart.js";
import { style } from "../../charts/src/grammar.js";
import { dumbbell } from "../../charts/src/dumbbell.js";
import { line } from "../../charts/src/line.js";
import { lexis } from "../../charts/src/lexis.js";
import { choropleth, symbols } from "../../charts/src/map.js";
import { pyramid } from "../../charts/src/pyramid.js";
import { tiles } from "../../charts/src/tiles.js";
import { waterfall } from "../../charts/src/waterfall.js";

// Fields of pipeline/src/grpop/provenance.py a value must carry to be quoted.
export const PROVENANCE = [
  "definition_id",
  "source",
  "dataset_code",
  "source_url",
  "vintage",
  "retrieved_at",
  "transform_version",
  "nature",
  "status",
];
const TYPES = { line, lexis, pyramid, dumbbell, waterfall, tiles, choropleth, symbols };
// Reference tables a spec may name (spec.layout), in data/reference.
const REFERENCE = new URL("../../data/reference/", import.meta.url);
const reference = (name) => {
  if (!/^[a-z0-9_]+$/.test(name)) throw new Error(`layout ${name}: not a reference table name`);
  return csvParse(readFileSync(new URL(`${name}.csv`, REFERENCE), "utf8"));
};
const LABELS = { el: { table: "Πίνακας δεδομένων", csv: "Λήψη CSV" }, en: { table: "Data table", csv: "Download CSV" } };

const typed = (r) => ({
  ...r,
  value: r.value === "" ? null : Number(r.value),
  break_in_series: r.break_in_series === "true",
  scenario_id: r.scenario_id || null,
  interval: r.interval || null,
});

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

function manifest(dir) {
  if (!dir) throw new Error("KOHORTES_DATA must name the data product directory (grpop-build --out)");
  return JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
}

/** Decimals of a derived indicator (the official value's rounding), or undefined. */
export const decimals = (dir, name) => manifest(dir)[name]?.decimals;
const formatOf = (dir, name) => (decimals(dir, name) === undefined ? {} : { maximumFractionDigits: decimals(dir, name) });

/** The bytes of one data product file, after checking it against the manifest. */
function checked(dir, name, file) {
  const listed = manifest(dir);
  if (!listed[name]?.files?.[file]) throw new Error(`${name}: not in the data product manifest, so it has no provenance`);
  const bytes = readFileSync(join(dir, file));
  if (sha256(bytes) !== listed[name].files[file]) throw new Error(`${file}: sha256 differs from the manifest`);
  return bytes;
}

/** A map geometry of the data product (GeoJSON with its source and licence). */
export const geometry = (dir, name) => JSON.parse(checked(dir, name, `${name}.geojson`).toString("utf8"));

/** The rows of one data product file, after checking it against the manifest. */
export function load(dir, name) {
  const bytes = checked(dir, name, `${name}.csv`);
  return csvParse(bytes.toString("utf8"), typed).map((r) => {
    if (Number.isNaN(r.value)) throw new Error(`${name} ${r.geo_code} ${r.period}: value is not a number`);
    const missing = PROVENANCE.filter((k) => !r[k]);
    if (missing.length) throw new Error(`${name} ${r.geo_code} ${r.period}: no ${missing.join(", ")}`);
    return r;
  });
}

const escape = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);

/**
 * One value as HTML: the formatted number, a visible note when it is provisional or not
 * observed fact (projected, scenario), and its source in the title.
 */
export function fact(dir, name, geo, period, sex = "total", age = "total", locale = "el-GR") {
  const t = TEXT[locale.slice(0, 2)];
  const rows = load(dir, name).filter(
    (r) => r.geo_code === geo && r.period === period && r.sex === sex && r.age === age && !r.interval && !r.scenario_id,
  );
  const where = `${name} ${geo} ${period} (sex ${sex}, age ${age})`;
  if (rows.length !== 1) throw new Error(`${where}: ${rows.length} values in the data product, need exactly one`);
  const [r] = rows;
  if (r.value === null) throw new Error(`${where}: ${r.status}`);
  const { dash, hollow } = style(r.nature, r.status);
  const notes = [dash && t.nature[r.nature], hollow && t.status[r.status]].filter(Boolean);
  const text = formatNumber(r.value, formatOf(dir, name), locale) + (notes.length ? ` (${notes.join(", ")})` : "");
  const title = `${t.source}: ${r.source} · ${r.dataset_code} · ${t.vintage} ${vintageDate(r.vintage)}`;
  return `<span class="fact" title="${escape(title)}">${escape(text)}</span>`;
}

/**
 * A chart from a JSON spec: {type, data, geo: [...], sex?, age?, ...the chart's spec}. The
 * figure in the light and the dark mode (styles.css shows the one Quarto is in), its data
 * table and its CSV.
 */
export function chart(dir, spec) {
  const { type, data, geo, sex = "total", age, ...given } = spec;
  const draw = TYPES[type];
  if (!draw) throw new Error(`chart type ${type}: the site draws ${Object.keys(TYPES).join(", ")}`);
  // A spec names its geometry (a data product file) and layout (a reference table).
  const rest = {
    format: formatOf(dir, data),
    ...given,
    ...(given.geometry && { geometry: geometry(dir, given.geometry) }),
    ...(given.layout && { layout: reference(given.layout) }),
  };
  const rows = load(dir, data).filter((r) => geo.includes(r.geo_code) && r.sex === sex && (age === undefined || r.age === age));
  const { window } = new JSDOM("");
  try {
    const modes = hexTokens();
    const [light, dark] = ["light", "dark"].map((m) => draw(rows, rest, { tokens: modes[m], document: window.document }));
    const l = LABELS[(rest.locale ?? "el").slice(0, 2)];
    const href = `data:text/csv;charset=utf-8,${encodeURIComponent(light.csv)}`;
    return [
      `<div class="kh-chart">`,
      `<div class="kh-light">${light.figure.outerHTML}</div>`,
      `<div class="kh-dark">${dark.figure.outerHTML}</div>`,
      `<details><summary>${l.table}</summary>${light.table.outerHTML}</details>`,
      `<p><a download="${escape(data)}.csv" href="${href}">${l.csv}</a></p>`,
      `</div>`,
    ].join("");
  } finally {
    window.close(); // a live jsdom window keeps node running
  }
}
