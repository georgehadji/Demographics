// What every chart returns (ADR 0005): the figure, a data table, alt text derived from
// the data and the CSV of exactly what is drawn. Rows are observations of the data
// product (pipeline/src/grpop/provenance.py); a chart type supplies only its figure.
import { formatNumber } from "../../design/src/format.js";
import { style } from "./grammar.js";

const REQUIRED = ["geo_code", "period", "value", "unit", "nature", "status", "source", "dataset_code", "vintage"];
const COLUMNS = ["geo_code", "period", "value", "unit", "nature", "status"];

export const TEXT = {
  el: {
    source: "Πηγή",
    vintage: "έκδοση",
    from: "από",
    to: "σε",
    provisional: "προσωρινές τιμές",
    missing: "—",
    yes: "ναι",
    columns: {
      geo_code: "Περιοχή",
      period: "Περίοδος",
      value: "Τιμή",
      unit: "Μονάδα",
      nature: "Φύση",
      status: "Κατάσταση",
      scenario_id: "Σενάριο",
      break_in_series: "Διακοπή σειράς",
    },
    nature: {
      observed: "παρατήρηση",
      official_estimate: "επίσημη εκτίμηση",
      derived: "παράγωγος δείκτης",
      projected: "προβολή",
      scenario: "σενάριο",
    },
    status: { final: "οριστική", revised: "αναθεωρημένη", provisional: "προσωρινή", not_available: "μη διαθέσιμη" },
  },
  en: {
    source: "Source",
    vintage: "vintage",
    from: "from",
    to: "to",
    provisional: "provisional values",
    missing: "—",
    yes: "yes",
    columns: {
      geo_code: "Area",
      period: "Period",
      value: "Value",
      unit: "Unit",
      nature: "Nature",
      status: "Status",
      scenario_id: "Scenario",
      break_in_series: "Break in series",
    },
    nature: {
      observed: "observed",
      official_estimate: "official estimate",
      derived: "derived",
      projected: "projection",
      scenario: "scenario",
    },
    status: { final: "final", revised: "revised", provisional: "provisional", not_available: "not available" },
  },
};

/** Chart settings shared by every type, with defaults filled in. */
export function settings(rows, spec) {
  if (!Array.isArray(rows) || rows.length === 0) throw new Error("a chart needs at least one row");
  for (const row of rows) {
    const missing = REQUIRED.filter((k) => !(k in row));
    if (missing.length) throw new Error(`row lacks ${missing.join(", ")}: ${JSON.stringify(row)}`);
    style(row.nature, row.status); // throws on an unknown vocabulary
    if (row.status === "not_available" ? row.value !== null : !Number.isFinite(row.value))
      throw new Error(`value must be a finite number, null exactly when status is not_available: ${JSON.stringify(row)}`);
  }
  const units = unique(rows, "unit");
  if (units.length > 1) throw new Error(`one unit per chart, no dual axes: ${units.join(", ")}`);
  const locale = spec.locale ?? "el-GR";
  const text = TEXT[locale.slice(0, 2)];
  if (!text) throw new Error(`no chart text for locale ${locale}`);
  const focus = spec.focus ?? "EL";
  if (!rows.some((r) => r.geo_code === focus)) throw new Error(`focus ${focus} is not in the data`);
  if (!spec.title) throw new Error("the title states the finding (PROPOSAL §7A)");
  const label = (geo) => spec.labels?.[geo] ?? geo;
  const format = (v) => (v === null ? text.missing : formatNumber(v, spec.format, locale));
  return { ...spec, locale, text, focus, label, format, unit: units[0] };
}

/** "Source: Eurostat · demo_gind · vintage 2026-09-15 · observed" from the rows. */
export function footer(rows, s) {
  const natures = unique(rows, "nature").map((n) => s.text.nature[n]);
  return [
    `${s.text.source}: ${unique(rows, "source").join(", ")}`,
    unique(rows, "dataset_code").join(", "),
    `${s.text.vintage} ${unique(rows, "vintage").join(", ")}`,
    natures.join(", "),
  ].join(" · ");
}

/**
 * Each series' first and last value, focus first, e.g. "Ελλάδα: από 10.816.286 (2011) σε
 * 9.500.000 (2050, προβολή)". The end names its nature when it differs from the start;
 * a scenario is named as one, never as the area's value.
 */
export function alt(rows, s) {
  const series = [...Map.groupBy(rows, seriesKey).values()].sort(
    (p, q) => (q[0].geo_code === s.focus) - (p[0].geo_code === s.focus),
  );
  const parts = series.map((part) => {
    const id = part[0].scenario_id;
    const name = s.label(part[0].geo_code) + (id ? ` (${s.text.nature.scenario}: ${id})` : "");
    const drawn = byPeriod(part.filter((r) => r.value !== null));
    if (drawn.length === 0) return `${name}: ${s.text.missing}`;
    const [a, b] = [drawn[0], drawn.at(-1)];
    const end = b.nature === a.nature ? b.period : `${b.period}, ${s.text.nature[b.nature]}`;
    return `${name}: ${s.text.from} ${s.format(a.value)} (${a.period}) ${s.text.to} ${s.format(b.value)} (${end})`;
  });
  const provisional = byPeriod(rows.filter((r) => r.geo_code === s.focus && r.status === "provisional"));
  if (provisional.length) parts.push(`${s.text.provisional}: ${provisional.map((r) => r.period).join(", ")}`);
  return `${s.title}. ${parts.join("; ")}.`;
}

/** RFC 4180 CSV of the rows as given, raw values, every column. */
export function csv(rows) {
  const columns = [...new Set(rows.flatMap(Object.keys))];
  const cell = (v) => {
    const t = v === null || v === undefined ? "" : v instanceof Date ? v.toISOString() : String(v);
    return /[",\r\n]/.test(t) ? `"${t.replaceAll('"', '""')}"` : t;
  };
  return [columns, ...rows.map((r) => columns.map((c) => r[c]))].map((line) => line.map(cell).join(",")).join("\n") + "\n";
}

/** The data-table view: one row per value, formatted for reading. */
export function table(rows, s, document) {
  const el = (tag, text) => Object.assign(document.createElement(tag), text === undefined ? {} : { textContent: text });
  const t = el("table");
  t.append(el("caption", s.title));
  const columns = [
    ...COLUMNS,
    ...(rows.some((r) => r.scenario_id) ? ["scenario_id"] : []),
    ...(rows.some((r) => r.break_in_series) ? ["break_in_series"] : []),
  ];
  const head = el("tr");
  for (const c of columns) head.append(Object.assign(el("th", s.text.columns[c]), { scope: "col" }));
  const body = el("tbody");
  for (const r of byPeriod(rows)) {
    const tr = el("tr");
    const cells = {
      geo_code: s.label(r.geo_code),
      period: r.period,
      value: s.format(r.value),
      unit: r.unit,
      nature: s.text.nature[r.nature],
      status: s.text.status[r.status],
      scenario_id: r.scenario_id ?? "",
      break_in_series: r.break_in_series ? s.text.yes : "",
    };
    for (const c of columns) tr.append(el("td", cells[c]));
    body.append(tr);
  }
  const thead = el("thead");
  thead.append(head);
  t.append(thead, body);
  return t;
}

/** A chart type from its figure: (rows, settings, options) -> SVG figure element. */
export function compose(figure) {
  return (rows, spec, { tokens, document = globalThis.document }) => {
    if (!tokens) throw new Error("tokens of one mode are required (design/dist/tokens.js)");
    const s = settings(rows, spec);
    return {
      figure: figure(rows, s, { tokens, document, caption: footer(rows, s) }),
      table: table(rows, s, document),
      alt: alt(rows, s),
      csv: csv(rows),
    };
  };
}

export const unique = (rows, key) => [...new Set(rows.map((r) => r[key]))];
export const byPeriod = (rows) => [...rows].sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0));
/** One line: an area, or one scenario of it. */
export const seriesKey = (r) => `${r.geo_code}|${r.scenario_id ?? ""}`;
