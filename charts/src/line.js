// Line chart over time: the focus area in the accent, comparators neutral, labels on
// the lines (PROPOSAL §7A). Each series is cut into segments where its nature changes,
// so the grammar styles each part. A break in series leaves a gap in the focus' line;
// a comparator runs through it, since aggregates such as the EU-27 inherit the breaks
// of every member state and would fall apart. Every break carries the footnote mark. A scenario is its own series (an area's scenarios share colour and dash
// and are told apart by their labels) and starts at the area's last value before it.
// Where the grammar asks for bands and the rows carry interval bounds, the chart is a
// fan chart: 95% and 80% bands open from the last value before them, and a thin rule
// marks the focus' last observation.
import * as Plot from "@observablehq/plot";
import { BREAK_MARK, byPeriod, central, compose, frame, seriesKey, seriesName, tip } from "./chart.js";
import { style } from "./grammar.js";

// Approximate width of a label character and line height of labels, in pixels, at
// Plot's 10px font.
const LABEL_CHAR = 6;
const LABEL_GAP = 12;
const MARGIN_LEFT = 40; // Plot's default
// Radius, in pixels, of the invisible point that shows a value's tooltip under the pointer.
export const TIP_RADIUS = 5;
const BANDS = [
  ["95", "opacity-band-95"],
  ["80", "opacity-band-80"],
];
const PERIOD = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/;

export function date(period) {
  const [, y, m = "01", d = "01"] = PERIOD.exec(period) ?? [];
  if (!y) throw new Error(`unknown period: ${period}`);
  return new Date(Date.UTC(+y, +m - 1, +d));
}

/**
 * Rows of one series (area and scenario) split where the nature changes or, with `gaps`,
 * a break starts. A new nature continues from the last value before it (a projection
 * starts at the last observation); a break does not.
 */
function segments(rows, gaps) {
  const out = [];
  for (const row of byPeriod(rows)) {
    const last = out.at(-1);
    const from = last?.rows.findLast((r) => r.value !== null);
    const cut = gaps && row.break_in_series;
    if (last && last.nature === row.nature && !cut) last.rows.push(row);
    else if (from && !cut) out.push({ nature: row.nature, rows: [from, row] });
    else out.push({ nature: row.nature, rows: [row] });
  }
  return out;
}

/**
 * The value a scenario starts from: its area's last value before it (an observation
 * before a projection of another file at the same period), unless a break starts it.
 */
function scenarioStart(part, rows, gaps) {
  const start = byPeriod(part)[0];
  if (!start.scenario_id || (gaps && start.break_in_series)) return undefined;
  const before = rows.filter((r) => r.geo_code === start.geo_code && !r.scenario_id && r.value !== null && r.period < start.period);
  const latest = byPeriod(before).at(-1);
  const tied = before.filter((r) => r.period === latest?.period);
  return tied.find((r) => !style(r.nature, "final").dash) ?? latest;
}

/**
 * The marks of one series: a line per segment (a scenario starting at its area's last
 * value before it), hollow markers and break marks. `rows` are all central rows, for
 * that start; `facet` adds fx/fy channels in small multiples; `gaps` cuts the line at a
 * break in series (the focus' line, not a comparator's).
 */
export function seriesMarks(part, rows, { color, width, tokens, facet = {}, gaps = true, title }) {
  const parts = segments(part, gaps);
  const from = scenarioStart(part, rows, gaps);
  if (from) parts[0].rows.unshift(from);
  const at = { x: (r) => date(r.period), y: "value", ...facet };
  const marks = parts.map((seg) => {
    const dash = style(seg.nature, "final").dash;
    return Plot.lineY(seg.rows, {
      ...at,
      stroke: color(seg.nature),
      strokeWidth: width,
      strokeDasharray: dash ? tokens[dash] : null,
      strokeLinecap: "round",
    });
  });
  for (const r of part.filter((r) => style(r.nature, r.status).hollow))
    marks.push(Plot.dot([r], { ...at, r: 3.5, stroke: color(r.nature), strokeWidth: width, fill: tokens["color-background"] }));
  for (const r of part.filter((r) => r.break_in_series && r.value !== null))
    marks.push(Plot.text([r], { ...at, text: () => BREAK_MARK, dy: -8, fill: tokens["color-text-muted"] }));
  // one invisible point per value carrying its tooltip (fill-opacity 0 still takes the pointer)
  if (title)
    marks.push(Plot.dot(part.filter((r) => r.value !== null), { ...at, r: TIP_RADIUS, fill: color(part[0].nature), fillOpacity: 0, title }));
  return marks;
}

/** The 95% and 80% bands of one series, each opening from the last value before it (a scenario's: where its line starts). */
function bands(part, bounds, color, tokens, from) {
  const marks = [];
  for (const [level, opacity] of BANDS) {
    const bound = (side) =>
      new Map(bounds.filter((r) => r.interval === `${level}_${side}` && r.value !== null).map((r) => [r.period, r.value]));
    const [lower, upper] = [bound("lower"), bound("upper")];
    const shown = byPeriod(part).filter((r) => style(r.nature, "final").band && lower.has(r.period) && upper.has(r.period));
    if (!shown.length) continue;
    const band = shown.map((r) => ({ x: date(r.period), y1: lower.get(r.period), y2: upper.get(r.period), nature: r.nature }));
    const before = byPeriod(part.filter((r) => r.value !== null && r.period < shown[0].period)).at(-1) ?? from;
    if (before) band.unshift({ x: date(before.period), y1: before.value, y2: before.value, nature: shown[0].nature });
    const fill = color(shown[0].nature);
    marks.push(Plot.areaY(band, { x: "x", y1: "y1", y2: "y2", fill, fillOpacity: tokens[opacity] }));
    if (level === "95")
      for (const y of ["y1", "y2"]) marks.push(Plot.lineY(band, { x: "x", y, stroke: fill, strokeWidth: tokens["stroke-width-band-edge"] }));
  }
  return marks;
}

/** A thin rule at the focus' last observation, when projections follow it. */
function lastObserved(rows, s, tokens) {
  const focus = byPeriod(rows.filter((r) => r.geo_code === s.focus && !r.scenario_id && r.value !== null));
  const next = focus.findIndex((r) => r.nature === "projected");
  if (next < 1) return [];
  const last = focus[next - 1];
  const muted = tokens["color-text-muted"];
  return [
    Plot.ruleX([date(last.period)], { stroke: muted, strokeWidth: tokens["stroke-width-band-edge"] }),
    Plot.text([`${s.text.lastObserved} ${last.period}`], {
      x: [date(last.period)],
      frameAnchor: "top",
      textAnchor: "end",
      dx: -4,
      dy: 4,
      fill: muted,
    }),
  ];
}

function draw(all, s, options) {
  const { tokens } = options;
  const rows = central(all);
  const series = Map.groupBy(rows, seriesKey);
  const under = [Plot.gridY({ stroke: tokens["color-gridline"], strokeOpacity: 1 })];
  const marks = [];
  const labels = [];
  for (const [key, part] of series) {
    const focus = part[0].geo_code === s.focus;
    const base = focus ? tokens["color-accent"] : tokens["color-comparator"];
    const width = tokens[focus ? "stroke-width-focus" : "stroke-width-context"];
    const color = (nature) => tokens[style(nature, "final").color] ?? base;
    const gaps = part[0].geo_code === s.focus;
    const from = scenarioStart(part, rows, gaps);
    under.push(...bands(part, all.filter((r) => r.interval && seriesKey(r) === key), color, tokens, from));
    marks.push(...seriesMarks(part, rows, { color, width, tokens, gaps: part[0].geo_code === s.focus, title: (r) => tip(s, r) }));
    const end = byPeriod(part.filter((r) => r.value !== null)).at(-1);
    if (end) {
      const name = seriesName(s, end);
      labels.push({ x: date(end.period), y: end.value, name, fill: focus ? color(end.nature) : tokens["color-text-muted"] });
    }
  }
  let domain = {};
  let marginLeft;
  const plot = (extra) =>
    Plot.plot({
      ...frame(s, options),
      marginLeft,
      marginRight: Math.max(0, ...labels.map((l) => l.name.length)) * LABEL_CHAR + 12,
      x: { type: "utc", label: null },
      y: { label: s.unit, tickFormat: s.format, ...domain },
      marks: [...under, ...lastObserved(rows, s, tokens), ...marks, ...extra],
    });
  const y = plot([]).scale("y");
  domain = { domain: y.domain }; // labels must not move the scale they were placed on
  // room for the longest tick label (10.372.335 would be cut at Plot's default 40)
  marginLeft = Math.max(MARGIN_LEFT, ...y.domain.map((v) => s.format(v).length * LABEL_CHAR + 12));
  const x = plot([]).scale("x"); // with the final margins
  return plot(dodge(labels, x, y).map((l) => Plot.text([l], { x: "x", y: "y", text: "name", fill: l.fill, dx: 6, textAnchor: "start" })));
}

/**
 * Labels pushed apart vertically wherever their text would overlap (by pixel extent:
 * a label runs LABEL_CHAR per character to the right of its x), each group moved back
 * up when its lowest would leave the plot.
 */
function dodge(labels, x, y) {
  const bottom = Math.max(...y.range);
  const span = (l) => [x.apply(l.x), x.apply(l.x) + l.name.length * LABEL_CHAR + 6];
  const sorted = labels.map((l) => ({ ...l, px: y.apply(l.y) })).toSorted((a, b) => a.px - b.px);
  const placed = [];
  for (const l of sorted) {
    const [a, b] = span(l);
    const near = placed.filter((p) => {
      const [c, d] = span(p);
      return a < d && c < b;
    });
    for (const p of near) if (l.px < p.px + LABEL_GAP) l.px = p.px + LABEL_GAP;
    placed.push(l);
  }
  const shift = Math.max(0, ...placed.map((l) => l.px - bottom));
  return placed.map(({ px, ...l }) => ({ ...l, y: y.invert(px - shift) }));
}

export const line = compose(draw);
