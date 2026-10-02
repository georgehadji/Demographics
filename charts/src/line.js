// Line chart over time: the focus area in the accent, comparators neutral, labels on
// the lines (PROPOSAL §7A). Each series is cut into segments where its nature changes
// or the source flags a break in series, so the grammar styles each part and a break
// leaves a gap. A scenario is its own series (an area's scenarios share colour and dash
// and are told apart by their labels) and starts at the area's last value before it.
import * as Plot from "@observablehq/plot";
import { byPeriod, compose, seriesKey } from "./chart.js";
import { style } from "./grammar.js";

// Approximate width of a label character and line height of labels, in pixels, at
// Plot's 10px font.
const LABEL_CHAR = 6;
const LABEL_GAP = 12;
const PERIOD = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/;

function date(period) {
  const [, y, m = "01", d = "01"] = PERIOD.exec(period) ?? [];
  if (!y) throw new Error(`unknown period: ${period}`);
  return new Date(Date.UTC(+y, +m - 1, +d));
}

/**
 * Rows of one series (area and scenario) split where the nature changes or a break
 * starts. A new nature continues from the last value before it (a projection starts at
 * the last observation); a break does not.
 */
function segments(rows) {
  const out = [];
  for (const row of byPeriod(rows)) {
    const last = out.at(-1);
    if (last && last.nature === row.nature && !row.break_in_series) last.rows.push(row);
    else if (last && !row.break_in_series) out.push({ nature: row.nature, rows: [last.rows.at(-1), row] });
    else out.push({ nature: row.nature, rows: [row] });
  }
  return out;
}

function draw(rows, s, { tokens, document, caption }) {
  const series = Map.groupBy(rows, seriesKey);
  const marks = [Plot.gridY({ stroke: tokens["color-gridline"], strokeOpacity: 1 })];
  const labels = [];
  for (const part of series.values()) {
    const focus = part[0].geo_code === s.focus;
    const base = focus ? tokens["color-accent"] : tokens["color-comparator"];
    const width = tokens[focus ? "stroke-width-focus" : "stroke-width-context"];
    const color = (nature) => tokens[style(nature, "final").color] ?? base;
    const parts = segments(part);
    const start = byPeriod(part)[0];
    if (start.scenario_id && !start.break_in_series) {
      const before = rows.filter(
        (r) => r.geo_code === start.geo_code && !r.scenario_id && r.value !== null && r.period < start.period,
      );
      if (before.length) parts[0].rows.unshift(byPeriod(before).at(-1));
    }
    for (const seg of parts) {
      const dash = style(seg.nature, "final").dash;
      marks.push(
        Plot.lineY(seg.rows, {
          x: (r) => date(r.period),
          y: "value",
          stroke: color(seg.nature),
          strokeWidth: width,
          strokeDasharray: dash ? tokens[dash] : null,
          strokeLinecap: "round",
        }),
      );
    }
    for (const r of part.filter((r) => style(r.nature, r.status).hollow))
      marks.push(
        Plot.dot([r], {
          x: (r) => date(r.period),
          y: "value",
          r: 3.5,
          stroke: color(r.nature),
          strokeWidth: width,
          fill: tokens["color-background"],
        }),
      );
    const end = byPeriod(part.filter((r) => r.value !== null)).at(-1);
    if (end) {
      const name = s.label(end.geo_code) + (end.scenario_id ? ` (${end.scenario_id})` : "");
      labels.push({ x: date(end.period), y: end.value, name, fill: focus ? color(end.nature) : tokens["color-text-muted"] });
    }
  }
  const font = `"${tokens["font-family"]}", ${tokens["font-fallback"]}`;
  let domain = {};
  const plot = (extra) =>
    Plot.plot({
      document,
      title: s.title,
      subtitle: s.subtitle,
      caption,
      marginRight: Math.max(0, ...labels.map((l) => l.name.length)) * LABEL_CHAR + 12,
      style: { fontFamily: font, fontVariantNumeric: tokens["font-numeric"], background: tokens["color-background"], color: tokens["color-text"] },
      x: { type: "utc", label: null },
      y: { label: s.unit, tickFormat: s.format, ...domain },
      marks: [...marks, ...extra],
    });
  const y = plot([]).scale("y");
  domain = { domain: y.domain }; // labels must not move the scale they were placed on
  const figure = plot(dodge(labels, y).map((l) => Plot.text([l], { x: "x", y: "y", text: "name", fill: l.fill, dx: 6, textAnchor: "start" })));
  // Plot styles only the SVG; the title, subtitle and footer sit around it.
  Object.assign(figure.style, { fontFamily: font, color: tokens["color-text"], background: tokens["color-background"] });
  return figure;
}

/**
 * Labels at the same x pushed apart vertically so they do not overlap, and back up
 * when the lowest would leave the plot.
 * ponytail: only labels at the same period are dodged; labels at neighbouring periods
 * can still touch on a narrow chart. Dodge by pixel extent if that shows up.
 */
function dodge(labels, y) {
  const bottom = Math.max(...y.range);
  const out = [];
  for (const group of Map.groupBy(labels, (l) => +l.x).values()) {
    const px = group.map((l) => y.apply(l.y)).toSorted((a, b) => a - b);
    const sorted = group.toSorted((a, b) => y.apply(a.y) - y.apply(b.y));
    for (let i = 1; i < px.length; i++) px[i] = Math.max(px[i], px[i - 1] + LABEL_GAP);
    const shift = Math.max(0, px.at(-1) - bottom);
    sorted.forEach((l, i) => out.push({ ...l, y: y.invert(px[i] - shift) }));
  }
  return out;
}

export const line = compose(draw);
