// One HTML page per mode with every chart type, its table and its alt text, for the
// visual regression and accessibility tests (visual/charts.spec.js) and for looking at
// the charts. The rows are hand-written illustrations, not data.
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { hexTokens } from "../../design/src/build.js";
import { line } from "../src/line.js";
import { lexis } from "../src/lexis.js";
import { dumbbell } from "../src/dumbbell.js";
import { choropleth, symbols } from "../src/map.js";
import { pyramid } from "../src/pyramid.js";
import { tiles } from "../src/tiles.js";
import { waterfall } from "../src/waterfall.js";

const row = (geo_code, period, value, extra = {}) => ({
  geo_code,
  period: String(period),
  sex: "total",
  age: "total",
  value,
  unit: "%",
  nature: "observed",
  status: "final",
  break_in_series: false,
  scenario_id: null,
  interval: null,
  source: "illustration",
  dataset_code: "none",
  vintage: "test",
  ...extra,
});
const range = (a, b) => Array.from({ length: b - a + 1 }, (_, i) => a + i);
const LABELS = {
  EL: "Ελλάδα",
  PT: "Πορτογαλία",
  IT: "Ιταλία",
  EL30: "Αττική",
  EL41: "Βόρειο Αιγαίο",
  EL42: "Νότιο Αιγαίο",
  EL43: "Κρήτη",
  EL51: "Αν. Μακεδονία, Θράκη",
  EL52: "Κεντρική Μακεδονία",
  EL53: "Δυτική Μακεδονία",
  EL54: "Ήπειρος",
  EL61: "Θεσσαλία",
  EL62: "Ιόνια Νησιά",
  EL63: "Δυτική Ελλάδα",
  EL64: "Στερεά Ελλάδα",
  EL65: "Πελοπόννησος",
  ES: "Ισπανία",
  births: "Γεννήσεις",
  deaths: "Θάνατοι",
  migration: "Καθαρή μετανάστευση",
  change: "Μεταβολή",
};
const LAYOUT = (() => {
  const [head, ...lines] = readFileSync(new URL("../../data/reference/el_nuts2_tiles.csv", import.meta.url), "utf8")
    .trim()
    .split(/\r?\n/);
  const keys = head.split(",");
  return lines.map((l) => Object.fromEntries(l.split(",").map((v, i) => [keys[i], v])));
})();

const LINE = [
  ...range(2005, 2024).flatMap((y) => [
    row("EL", y, 26 + (y - 2005) * 0.6, y === 2024 ? { status: "provisional" } : y === 2012 ? { break_in_series: true } : {}),
    row("PT", y, 25 + (y - 2005) * 0.7),
    row("IT", y, 29 + (y - 2005) * 0.5),
  ]),
  ...range(2025, 2050).flatMap((y) => {
    const v = 37.4 + (y - 2024) * 0.8;
    const w = (y - 2024) * 0.25;
    return [
      row("EL", y, v, { nature: "projected" }),
      row("EL", y, v - 2 * w, { nature: "projected", interval: "95_lower" }),
      row("EL", y, v + 2 * w, { nature: "projected", interval: "95_upper" }),
      row("EL", y, v - w, { nature: "projected", interval: "80_lower" }),
      row("EL", y, v + w, { nature: "projected", interval: "80_upper" }),
      row("EL", y, 37.4 + (y - 2024) * 1.1, { nature: "scenario", scenario_id: "χαμηλή γονιμότητα" }),
    ];
  }),
];

const AGES = [...range(0, 17).map((i) => `${i * 5}-${i * 5 + 4}`), "90+"];
const PYRAMID = [2001, 2024].flatMap((year) =>
  AGES.flatMap((age, i) => {
    const peak = year === 2001 ? 7 : 10;
    const v = Math.round(400 * Math.exp(-(((i - peak) / 6) ** 2)) + 60);
    return ["male", "female"].map((sex) =>
      row("EL", year, (v + (sex === "female" ? i * 3 : 0)) * 1000, { sex, age, unit: "persons" }),
    );
  }),
);

const LEXIS = range(2012, 2024).flatMap((year) =>
  range(15, 49).map((age) => {
    const mean = 28 + (year - 2012) * 0.25;
    return row("EL", year, Math.round(1200 * Math.exp(-(((age - mean) / 5.5) ** 2))) / 10000, {
      age: String(age),
      unit: "γεννήσεις ανά γυναίκα",
      ...(year === 2024 ? { status: "provisional" } : {}),
    });
  }),
);

const TILES = ["EL", ...LAYOUT.map((t) => t.geo_code)].flatMap((geo, i) =>
  range(2011, 2024).map((y) => row(geo, y, 100 - (y - 2011) * (0.2 + (i % 5) * 0.15), { unit: "δείκτης, 2011 = 100" })),
);

/** Illustrative map: one square "region" per tile of the layout, not GISCO geometry. */
export const GEOMETRY = {
  type: "FeatureCollection",
  attribution: "Γεωμετρία: σχηματική, όχι πραγματικά όρια",
  features: LAYOUT.map(({ geo_code, row: r, col: c }) => {
    const [x, y] = [20 + +c, 41 - +r];
    return {
      type: "Feature",
      id: geo_code,
      properties: { geo_code },
      geometry: { type: "Polygon", coordinates: [[[x, y], [x, y - 0.9], [x + 0.9, y - 0.9], [x + 0.9, y], [x, y]]] },
    };
  }),
};
const RATES = LAYOUT.map(({ geo_code }, i) =>
  row(geo_code, 2024, 9 + ((i * 7) % 13) / 2, { unit: "per 1000 average population", ...(geo_code === "EL43" ? { status: "provisional" } : {}) }),
);
const COUNTS = LAYOUT.map(({ geo_code }, i) => row(geo_code, 2024, geo_code === "EL30" ? 3800000 : 180000 + ((i * 5) % 13) * 110000, { unit: "persons" }));

const DUMBBELL = [
  ["EL", 1.4, 1.24],
  ["PT", 1.35, 1.4],
  ["IT", 1.44, 1.18],
  ["ES", 1.34, 1.12],
].flatMap(([geo, a, b]) => [
  row(geo, 2011, a, { unit: "γεννήσεις ανά γυναίκα" }),
  row(geo, 2024, b, { unit: "γεννήσεις ανά γυναίκα", ...(geo === "EL" ? { status: "provisional" } : {}) }),
]);
const WATERFALL = [
  ["births", 70000],
  ["deaths", -125000],
  ["migration", 49000, { status: "provisional" }],
  ["change", -6000],
].map(([definition_id, v, extra = {}]) => row("EL", 2025, v, { definition_id, unit: "persons", ...extra }));

export const CHARTS = {
  line: [line, LINE, { title: "Η εξάρτηση των ηλικιωμένων αυξάνεται ταχύτερα από την Πορτογαλία", subtitle: "Δείκτης εξάρτησης ηλικιωμένων, %", format: { maximumFractionDigits: 0 } }],
  pyramid: [pyramid, PYRAMID, { title: "Η μεγαλύτερη ομάδα μετακινήθηκε 15 χρόνια μεγαλύτερη", subtitle: "Πληθυσμός κατά φύλο και ηλικία" }],
  lexis: [lexis, LEXIS, { title: "Η γονιμότητα μετατοπίζεται σε μεγαλύτερες ηλικίες", subtitle: "Γεννήσεις ανά γυναίκα, κατά ηλικία και έτος", format: { maximumFractionDigits: 2 } }],
  choropleth: [choropleth, RATES, { title: "Η θνησιμότητα είναι υψηλότερη στις αγροτικές περιφέρειες", subtitle: "Θάνατοι ανά 1.000 κατοίκους, 2024", focus: "EL30", geometry: GEOMETRY, format: { maximumFractionDigits: 1 } }],
  symbols: [symbols, COUNTS, { title: "Η Αττική συγκεντρώνει πάνω από το ένα τρίτο του πληθυσμού", subtitle: "Πληθυσμός, 2024", focus: "EL30", geometry: GEOMETRY }],
  dumbbell: [dumbbell, DUMBBELL, { title: "Η γονιμότητα έπεσε σε τρεις από τις τέσσερις", subtitle: "Γεννήσεις ανά γυναίκα, 2011 και 2024", format: { maximumFractionDigits: 2 } }],
  waterfall: [waterfall, WATERFALL, { title: "Οι θάνατοι ξεπερνούν γεννήσεις και μετανάστευση", subtitle: "Συνιστώσες της μεταβολής του πληθυσμού, 2025", parts: ["births", "deaths", "migration"], total: "change" }],
  tiles: [tiles, TILES, { title: "Όλες οι περιφέρειες χάνουν πληθυσμό", subtitle: "Πληθυσμός, 2011 = 100", layout: LAYOUT, format: { maximumFractionDigits: 0 } }],
};

/** The page for one mode (light, dark or print). */
export function page(mode) {
  const tokens = hexTokens()[mode];
  const { window } = new JSDOM("");
  const sections = Object.entries(CHARTS).map(([name, [type, rows, spec]]) => {
    const chart = type(rows, { ...spec, labels: LABELS }, { tokens, document: window.document });
    chart.table.querySelector("caption").textContent += " (πίνακας δεδομένων)";
    return `<section data-chart="${name}">${chart.figure.outerHTML}<details><summary>Πίνακας δεδομένων</summary>${chart.table.outerHTML}</details></section>`;
  });
  window.close();
  return `<!doctype html>
<html lang="el"><head><meta charset="utf-8"><title>Charts, ${mode}</title>
<style>
body { margin: 0; background: ${tokens["color-background"]}; color: ${tokens["color-text"]}; font-family: "${tokens["font-family"]}", ${tokens["font-fallback"]}; }
main { padding: 16px; }
section { margin: 0 0 32px; width: max-content; }
summary { font-size: ${tokens["font-size-small"]}; }
table { border-collapse: collapse; font-variant-numeric: ${tokens["font-numeric"]}; }
td, th { padding: 2px 8px; border-bottom: 1px solid ${tokens["color-gridline"]}; }
</style></head>
<body><main><h1>Charts, ${mode}</h1>${sections.join("\n")}</main></body></html>
`;
}
