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
import { TEXT } from "../../charts/src/chart.js";
import { style } from "../../charts/src/grammar.js";
import { line } from "../../charts/src/line.js";
import { lexis } from "../../charts/src/lexis.js";
import { pyramid } from "../../charts/src/pyramid.js";

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
// ponytail: types whose spec is plain JSON; maps and tiles need geometry or a layout, add
// them when a page uses one.
const TYPES = { line, lexis, pyramid };
const LABELS = { el: { table: "Πίνακας δεδομένων", csv: "Λήψη CSV" }, en: { table: "Data table", csv: "Download CSV" } };

const typed = (r) => ({
  ...r,
  value: r.value === "" ? null : Number(r.value),
  break_in_series: r.break_in_series === "true",
  scenario_id: r.scenario_id || null,
  interval: r.interval || null,
});

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

/** The rows of one data product file, after checking it against the manifest. */
export function load(dir, name) {
  if (!dir) throw new Error("KOHORTES_DATA must name the data product directory (grpop-build --out)");
  const manifest = JSON.parse(readFileSync(join(dir, "manifest.json"), "utf8"));
  const file = `${name}.csv`;
  if (!manifest[name]?.files?.[file]) throw new Error(`${name}: not in the data product manifest, so it has no provenance`);
  const bytes = readFileSync(join(dir, file));
  if (sha256(bytes) !== manifest[name].files[file]) throw new Error(`${file}: sha256 differs from the manifest`);
  return csvParse(bytes.toString("utf8"), typed).map((r) => {
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
  const text = formatNumber(r.value, {}, locale) + (notes.length ? ` (${notes.join(", ")})` : "");
  const title = `${t.source}: ${r.source} · ${r.dataset_code} · ${t.vintage} ${r.vintage}`;
  return `<span class="fact" title="${escape(title)}">${escape(text)}</span>`;
}

/**
 * A chart from a JSON spec: {type, data, geo: [...], sex?, age?, ...the chart's spec}. The
 * figure in the light and the dark mode (styles.css shows the one Quarto is in), its data
 * table and its CSV.
 */
export function chart(dir, spec) {
  const { type, data, geo, sex = "total", age, ...rest } = spec;
  const draw = TYPES[type];
  if (!draw) throw new Error(`chart type ${type}: the site draws ${Object.keys(TYPES).join(", ")}`);
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
