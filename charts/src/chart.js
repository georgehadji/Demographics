// What every chart returns (ADR 0005): the figure, a data table, alt text derived from
// the data and the CSV of exactly what is drawn. Rows are observations of the data
// product (pipeline/src/grpop/provenance.py); a chart type supplies its figure and,
// when the default does not describe it, its alt text.
import { formatNumber } from "../../design/src/format.js";
import { style } from "./grammar.js";

const REQUIRED = [
  "geo_code",
  "period",
  "sex",
  "age",
  "value",
  "unit",
  "nature",
  "status",
  "source",
  "dataset_code",
  "vintage",
];
// Table columns in order; the optional ones are shown only when some row needs them.
const COLUMNS = ["geo_code", "definition_id", "period", "sex", "age", "value", "unit", "nature", "status", "scenario_id", "interval", "break_in_series"];
// Optional columns: shown when a row needs them (the measure, when rows hold more than one).
const OPTIONAL = {
  definition_id: (r, rows) => r.definition_id !== rows[0].definition_id,
  sex: (r) => r.sex !== "total",
  age: (r) => r.age !== "total",
  scenario_id: (r) => r.scenario_id,
  interval: (r) => r.interval,
  break_in_series: (r) => r.break_in_series,
};

export const TEXT = {
  el: {
    source: "Πηγή",
    vintage: "έκδοση",
    from: "από",
    to: "σε",
    provisional: "προσωρινές τιμές",
    break: "διακοπή σειράς",
    lastObserved: "τελευταία παρατήρηση",
    largest: "μεγαλύτερη ομάδα",
    outline: "περίγραμμα",
    central: "κεντρική τιμή",
    classes: { quantize: "ίσα διαστήματα", quantile: "ποσοστημόρια" },
    reference: "λεπτή γραμμή",
    highest: "υψηλότερη τιμή",
    lowest: "χαμηλότερη τιμή",
    sign: { negative: "αρνητική τιμή", positive: "θετική τιμή" },
    age: "ηλικία",
    missing: "—",
    yes: "ναι",
    total: "σύνολο",
    columns: {
      geo_code: "Περιοχή",
      definition_id: "Μέγεθος",
      period: "Περίοδος",
      sex: "Φύλο",
      age: "Ηλικία",
      value: "Τιμή",
      unit: "Μονάδα",
      nature: "Φύση",
      status: "Κατάσταση",
      scenario_id: "Σενάριο",
      interval: "Διάστημα",
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
    sex: { total: "σύνολο", male: "άνδρες", female: "γυναίκες" },
    interval: { "80_lower": "κάτω όριο 80%", "80_upper": "άνω όριο 80%", "95_lower": "κάτω όριο 95%", "95_upper": "άνω όριο 95%" },
    // the units of pipeline/src/grpop/definitions.yaml (test/grammar.test.js checks them all)
    units: {
      "% of persons of known age": "% των ατόμων γνωστής ηλικίας",
      "deaths per person-year": "θάνατοι ανά ανθρωποέτος",
      probability: "πιθανότητα",
      "live births per woman": "γεννήσεις ζώντων ανά γυναίκα",
      "males per 100 females": "άνδρες ανά 100 γυναίκες",
      "per 100 persons aged 0-14": "ανά 100 άτομα 0–14 ετών",
      "per 100 persons aged 15-64": "ανά 100 άτομα 15–64 ετών",
      "per 1000 average population": "ανά 1.000 κατοίκους (μέσος πληθυσμός)",
      "per 1000 live births": "ανά 1.000 γεννήσεις ζώντων",
      "per 1000 total births": "ανά 1.000 συνολικές γεννήσεις (ζώντων και νεκρών)",
      "per 100 marriages": "ανά 100 γάμους",
      "first marriages per person": "πρώτοι γάμοι ανά άτομο",
      marriages: "γάμοι",
      "civil partnerships": "σύμφωνα συμβίωσης",
      divorces: "διαζύγια",
      stillbirths: "γεννήσεις νεκρών",
      persons: "άτομα",
      years: "έτη",
    },
  },
  en: {
    source: "Source",
    vintage: "vintage",
    from: "from",
    to: "to",
    provisional: "provisional values",
    break: "break in series",
    lastObserved: "last observation",
    largest: "largest group",
    outline: "outline",
    central: "central value",
    classes: { quantize: "equal intervals", quantile: "quantiles" },
    reference: "thin line",
    highest: "highest value",
    lowest: "lowest value",
    sign: { negative: "negative value", positive: "positive value" },
    age: "age",
    missing: "—",
    yes: "yes",
    total: "total",
    columns: {
      geo_code: "Area",
      definition_id: "Measure",
      period: "Period",
      sex: "Sex",
      age: "Age",
      value: "Value",
      unit: "Unit",
      nature: "Nature",
      status: "Status",
      scenario_id: "Scenario",
      interval: "Interval",
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
    sex: { total: "total", male: "men", female: "women" },
    interval: { "80_lower": "80% lower bound", "80_upper": "80% upper bound", "95_lower": "95% lower bound", "95_upper": "95% upper bound" },
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
  // null: no area in the foreground (e.g. a map of all regions)
  const focus = spec.focus === undefined ? "EL" : spec.focus;
  if (focus !== null && !rows.some((r) => r.geo_code === focus)) throw new Error(`focus ${focus} is not in the data`);
  if (!spec.title) throw new Error("the title states the finding (PROPOSAL §7A)");
  // names of areas and scenarios, by geo_code or scenario_id
  const label = (key) => spec.labels?.[key] ?? key;
  const format = (v) => (v === null ? text.missing : formatNumber(v, spec.format, locale));
  // the unit in the chart's language; units in that language already (or English) as given
  return { ...spec, locale, text, focus, label, format, unit: text.units?.[units[0]] ?? units[0] };
}

/** "Source: Eurostat · demo_gind · vintage 2026-09-15 · observed", plus the breaks in series. */
export function footer(rows, s) {
  const parts = [
    `${s.text.source}: ${unique(rows, "source").join(", ")}`,
    unique(rows, "dataset_code").join(", "),
    `${s.text.vintage} ${unique(rows.map((r) => ({ v: vintageDate(r.vintage) })), "v").join(", ")}`,
    unique(rows, "nature")
      .map((n) => s.text.nature[n])
      .join(", "),
  ];
  const breaks = breaksIn(rows, s);
  if (breaks.length) parts.push(`${BREAK_MARK} ${s.text.break}: ${breaks.join(", ")}`);
  return parts.join(" · ");
}

/**
 * Each series' first and last central value, focus first, e.g. "Ελλάδα: από 10.816.286
 * (2011) σε 9.500.000 (2050, προβολή)". The end names its nature when it differs from the
 * start; a scenario is named as one, never as the area's value.
 */
export function seriesAlt(rows, s, { focusFirst = true } = {}) {
  const sign = focusFirst ? 1 : -1;
  const series = [...Map.groupBy(central(rows), seriesKey).values()].sort(
    // focus first (or last), and an area's own series before its scenarios
    (p, q) => sign * ((q[0].geo_code === s.focus) - (p[0].geo_code === s.focus)) || !!p[0].scenario_id - !!q[0].scenario_id,
  );
  const parts = series.map((part) => {
    const id = part[0].scenario_id;
    const name = s.label(part[0].geo_code) + (id ? ` (${s.text.nature.scenario}: ${s.label(id)})` : "");
    const drawn = byPeriod(part.filter((r) => r.value !== null));
    if (drawn.length === 0) return `${name}: ${s.text.missing}`;
    const [a, b] = [drawn[0], drawn.at(-1)];
    const end = b.nature === a.nature ? b.period : `${b.period}, ${s.text.nature[b.nature]}`;
    const bound = (side) => rows.find((r) => seriesKey(r) === seriesKey(b) && r.period === b.period && r.interval === `95_${side}`);
    const [low, high] = [bound("lower"), bound("upper")];
    const band = low?.value != null && high?.value != null ? `, 95%: ${s.format(low.value)}–${s.format(high.value)}` : "";
    return `${name}: ${s.text.from} ${s.format(a.value)} (${a.period}) ${s.text.to} ${s.format(b.value)} (${end}${band})`;
  });
  return sentence(s, parts, rows);
}

/** Title, parts, the focus' provisional periods and the breaks in series as one alt text. */
export function sentence(s, parts, rows) {
  const provisional = unique(byPeriod(rows.filter((r) => r.geo_code === s.focus && r.status === "provisional")), "period");
  if (provisional.length) parts.push(`${s.text.provisional}: ${provisional.join(", ")}`);
  const breaks = breaksIn(rows, s);
  if (breaks.length) parts.push(`${s.text.break}: ${breaks.join(", ")}`);
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
  const columns = COLUMNS.filter((c) => !OPTIONAL[c] || rows.some((r) => OPTIONAL[c](r, rows)));
  const head = el("tr");
  for (const c of columns) head.append(Object.assign(el("th", s.text.columns[c]), { scope: "col" }));
  const body = el("tbody");
  for (const r of byPeriod(rows)) {
    const tr = el("tr");
    const cells = {
      geo_code: s.label(r.geo_code),
      definition_id: s.label(r.definition_id),
      period: r.period,
      sex: s.text.sex[r.sex],
      age: r.age,
      value: s.format(r.value),
      unit: s.unit,
      nature: s.text.nature[r.nature],
      status: s.text.status[r.status],
      scenario_id: r.scenario_id ? s.label(r.scenario_id) : "",
      interval: r.interval ? s.text.interval[r.interval] : s.text.central,
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

/**
 * A chart type from its figure, (rows, settings, {tokens, document, caption}) -> figure
 * element, and its alt text, (rows, settings) -> string.
 */
export function compose(figure, describe = seriesAlt) {
  return (rows, spec, { tokens, document = globalThis.document }) => {
    if (!tokens) throw new Error("tokens of one mode are required (design/dist/tokens.js)");
    const s = settings(rows, spec);
    const fig = figure(rows, s, { tokens, document, caption: footer(rows, s) });
    // Plot styles only the SVG; the title, subtitle, legend and footer sit around it.
    Object.assign(fig.style, {
      fontFamily: `"${tokens["font-family"]}", ${tokens["font-fallback"]}`,
      color: tokens["color-text"],
      background: tokens["color-background"],
    });
    const alt = describe(rows, s);
    // The plot is one image to assistive technology, described by the alt text; the
    // table carries the values.
    const svg = [...fig.querySelectorAll("svg")].at(-1);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", alt);
    // Plot names its mark groups with aria-label, which ARIA forbids on plain groups;
    // keep the name as data-mark.
    for (const g of svg.querySelectorAll("[aria-label]")) {
      g.setAttribute("data-mark", g.getAttribute("aria-label"));
      g.removeAttribute("aria-label");
    }
    return { figure: fig, table: table(rows, s, document), alt, csv: csv(rows) };
  };
}

/** Plot options every chart shares: document, title, subtitle, footer and type. */
export function frame(s, { tokens, document, caption }) {
  return {
    document,
    title: s.title,
    subtitle: s.subtitle,
    caption,
    style: {
      fontFamily: `"${tokens["font-family"]}", ${tokens["font-fallback"]}`,
      fontVariantNumeric: tokens["font-numeric"],
      background: tokens["color-background"],
      color: tokens["color-text"],
    },
  };
}

/** "Ελλάδα 2012" for each break in series. */
const breaksIn = (rows, s) => [
  ...new Set(byPeriod(central(rows).filter((r) => r.break_in_series)).map((r) => `${s.label(r.geo_code)} ${r.period}`)),
];

/** Plot options of a bar in the grammar: projected lighter with a dashed edge, provisional hollow. */
export function barLook(r, color, tokens) {
  const look = style(r.nature, r.status);
  return {
    fill: look.hollow ? tokens["color-background"] : color,
    fillOpacity: look.dash ? tokens["opacity-band-80"] : 1,
    stroke: color,
    strokeWidth: look.hollow || look.dash ? tokens["stroke-width-context"] : 0,
    strokeDasharray: look.dash ? tokens[look.dash] : null,
  };
}

/**
 * The tooltip of one value (PROPOSAL §7A): area, period, value and unit, nature and
 * status, source and dataset. Drawn as the SVG's own title, so it needs no script; the
 * data table carries the same fields for the keyboard.
 */
export const tip = (s, r) =>
  `${s.label(r.geo_code)}${r.scenario_id ? ` (${s.label(r.scenario_id)})` : ""} ${r.period}: ${s.format(r.value)} ${s.unit}` +
  ` · ${s.text.nature[r.nature]}, ${s.text.status[r.status]} · ${r.source}, ${r.dataset_code}`;

/** ", προβολή" after a value that is projected or a scenario, so it is never read as observed. */
export const natureNote = (s, r) => (style(r.nature, "final").dash ? `, ${s.text.nature[r.nature]}` : "");

/** A vintage that is a timestamp ("2026-09-30T23:00:00+0200") as its date; others as given. */
export const vintageDate = (v) => (/^\d{4}-\d{2}-\d{2}T/.test(v) ? v.slice(0, 10) : v);

// Marks a break in series on the figure and in the footer.
export const BREAK_MARK = "*";
export const unique = (rows, key) => [...new Set(rows.map((r) => r[key]))];
export const byPeriod = (rows) => [...rows].sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0));
/** Central values only: interval bounds are drawn as bands, never as values. */
export const central = (rows) => rows.filter((r) => !r.interval);
/** One line: an area, or one scenario of it. */
export const seriesKey = (r) => `${r.geo_code}|${r.scenario_id ?? ""}`;
/** Lower bound of an age ("85+" -> 85, "15-64" -> 15, "7" -> 7); null for total and unknown. */
export const ageStart = (age) => (/^\d/.test(age) ? Number.parseInt(age, 10) : null);
