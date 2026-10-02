// One HTML page per mode with every chart type, its table and its alt text, for the
// visual regression and accessibility tests (visual/charts.spec.js) and for looking at
// the charts. The rows are hand-written illustrations, not data.
import { readFileSync } from "node:fs";
import { JSDOM } from "jsdom";
import { hexTokens } from "../../design/src/build.js";
import { line } from "../src/line.js";
import { lexis } from "../src/lexis.js";
import { pyramid } from "../src/pyramid.js";
import { tiles } from "../src/tiles.js";

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

const LEXIS = range(2004, 2024).flatMap((year) =>
  range(15, 49).map((age) => {
    const mean = 27 + (year - 2004) * 0.2;
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

export const CHARTS = {
  line: [line, LINE, { title: "Η εξάρτηση των ηλικιωμένων αυξάνεται ταχύτερα από την Πορτογαλία", subtitle: "Δείκτης εξάρτησης ηλικιωμένων, %", format: { maximumFractionDigits: 0 } }],
  pyramid: [pyramid, PYRAMID, { title: "Η μεγαλύτερη ομάδα μετακινήθηκε 15 χρόνια μεγαλύτερη", subtitle: "Πληθυσμός κατά φύλο και ηλικία" }],
  lexis: [lexis, LEXIS, { title: "Η γονιμότητα μετατοπίζεται σε μεγαλύτερες ηλικίες", subtitle: "Γεννήσεις ανά γυναίκα, κατά ηλικία και έτος", format: { maximumFractionDigits: 2 } }],
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
