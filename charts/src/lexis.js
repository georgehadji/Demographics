// Lexis surface (PROPOSAL §7A): a rate by single year of age (rows) and calendar year
// (columns) in one area, with diagonal lines along birth cohorts every ten years. Colour
// classes come from the design palettes, sequential by default or diverging around 0
// (spec.palette); the classification is equal intervals (spec.classes "quantize",
// default) or quantiles ("quantile") and is named in the legend. Provisional cells are
// outlined; a rule marks where projections start.
import * as Plot from "@observablehq/plot";
import { ageStart, compose, frame, natureNote, sentence, unique } from "./chart.js";
import { style } from "./grammar.js";

const COHORT_STEP = 10;
const CLASSES = ["quantize", "quantile"];

function cells(rows, s) {
  if (unique(rows, "geo_code").length > 1) throw new Error("a Lexis surface shows one area");
  if (unique(rows, "sex").length > 1) throw new Error("a Lexis surface shows one sex");
  for (const r of rows) {
    if (!/^\d{4}$/.test(r.period)) throw new Error(`a Lexis surface needs calendar years, not ${r.period}`);
    // An open-ended age ("85+") is not one year wide and has no cohort diagonal.
    if (!/^\d+$/.test(r.age)) throw new Error(`a Lexis surface needs single years of age, not ${r.age}`);
    if (r.interval) throw new Error("a Lexis surface draws central values only");
  }
  if (!CLASSES.includes(s.classes ?? "quantize")) throw new Error(`unknown classification ${s.classes}`);
  return rows.map((r) => ({ ...r, year: +r.period, a: ageStart(r.age) }));
}

function draw(rows, s, options) {
  const { tokens } = options;
  const data = cells(rows, s);
  const drawn = data.filter((r) => r.value !== null);
  const [y0, y1] = [Math.min(...data.map((r) => r.year)), Math.max(...data.map((r) => r.year)) + 1];
  const [a0, a1] = [Math.min(...data.map((r) => r.a)), Math.max(...data.map((r) => r.a)) + 1];
  const box = { x1: "year", x2: (r) => r.year + 1, y1: "a", y2: (r) => r.a + 1 };
  const cohorts = [];
  for (let b = Math.ceil((y0 - a1) / COHORT_STEP) * COHORT_STEP; b <= y1 - a0; b += COHORT_STEP)
    cohorts.push({ b, points: [{ x: b + a0, y: a0 }, { x: b + a1, y: a1 }] });
  const diverging = s.palette === "diverging";
  const extent = Math.max(...drawn.map((r) => Math.abs(r.value)));
  const projected = data.filter((r) => r.nature === "projected").map((r) => r.year);
  const muted = tokens["color-text-muted"];
  return Plot.plot({
    ...frame(s, options),
    x: { domain: [y0, y1], label: null, tickFormat: (v) => String(v) },
    y: { domain: [a0, a1], label: s.text.columns.age },
    color: {
      type: s.classes ?? "quantize",
      range: tokens[diverging ? "palette-diverging" : "palette-sequential"],
      ...(diverging && (s.classes ?? "quantize") === "quantize" ? { domain: [-extent, extent] } : {}),
      legend: true,
      label: `${s.unit} · ${s.text.classes[s.classes ?? "quantize"]}`,
      tickFormat: s.format,
    },
    marks: [
      Plot.rect(drawn, { ...box, fill: "value" }),
      Plot.rect(
        drawn.filter((r) => style(r.nature, r.status).hollow),
        { ...box, fill: "none", stroke: tokens["color-boundary"], strokeWidth: tokens["stroke-width-boundary"], inset: 0.5 },
      ),
      ...cohorts.map(({ points }) =>
        Plot.line(points, { x: "x", y: "y", stroke: tokens["color-boundary"], strokeWidth: tokens["stroke-width-band-edge"], clip: true }),
      ),
      ...(projected.length
        ? [
            Plot.ruleX([Math.min(...projected)], { stroke: muted, strokeWidth: tokens["stroke-width-focus"] }),
            Plot.text([`${s.text.nature.projected} →`], { x: [Math.min(...projected)], frameAnchor: "top", textAnchor: "start", dx: 4, dy: 4, fill: muted }),
          ]
        : []),
    ],
  });
}

/** The highest and the lowest value, with their age and year. */
function describe(rows, s) {
  const drawn = rows.filter((r) => r.value !== null && !r.interval);
  if (!drawn.length) return sentence(s, [s.text.missing], rows);
  const at = (r) => `${s.format(r.value)} (${s.text.age} ${r.age}, ${r.period}${natureNote(s, r)})`;
  const high = drawn.reduce((a, b) => (b.value > a.value ? b : a));
  const low = drawn.reduce((a, b) => (b.value < a.value ? b : a));
  return sentence(s, [`${s.label(s.focus)}: ${s.text.highest} ${at(high)}`, `${s.text.lowest} ${at(low)}`], rows);
}

export const lexis = compose(draw, describe);
