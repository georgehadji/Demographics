// Change between two years (PROPOSAL §7A): one row per area, a small dot at the first
// year joined to a large dot at the second, areas sorted by the second value. The focus
// is in the accent, comparators neutral; the two years are labelled on the focus' row.
// The grammar styles the second value (projected: dashed link, provisional: hollow dot).
import * as Plot from "@observablehq/plot";
import { compose, frame, seriesAlt, unique } from "./chart.js";
import { style } from "./grammar.js";

// Approximate width of a label character, in pixels, at Plot's 10px font.
const LABEL_CHAR = 6;

/** The two periods and, per area, its [first, second] row, sorted by the second value. */
function pairs(rows) {
  for (const r of rows) {
    if (r.interval) throw new Error("a dumbbell draws central values only");
    if (r.scenario_id) throw new Error("a dumbbell compares observed or projected values, not scenarios");
  }
  const periods = unique(rows, "period").sort();
  if (periods.length !== 2) throw new Error(`a dumbbell compares two periods, not ${periods.join(", ")}`);
  const list = [...Map.groupBy(rows, (r) => r.geo_code)].map(([geo, g]) => {
    if (g.length !== 2 || g.some((r) => r.value === null)) throw new Error(`${geo}: needs one value in each of ${periods.join(" and ")}`);
    return [...g].sort((a, b) => (a.period < b.period ? -1 : 1));
  });
  return { periods, list: list.sort((p, q) => q[1].value - p[1].value) };
}

function draw(rows, s, options) {
  const { tokens } = options;
  const { periods, list } = pairs(rows);
  const focused = (r) => r.geo_code === s.focus;
  const color = (r) => tokens[focused(r) ? "color-accent" : "color-comparator"];
  const y = (r) => s.label(r.geo_code);
  const focus = list.find(([a]) => focused(a)) ?? [];
  return Plot.plot({
    ...frame(s, options),
    marginLeft: Math.max(...list.map(([a]) => y(a).length)) * LABEL_CHAR + 12,
    x: { label: s.unit, tickFormat: s.format },
    y: { label: null, domain: list.map(([a]) => y(a)) },
    marks: [
      Plot.gridX({ stroke: tokens["color-gridline"], strokeOpacity: 1 }),
      ...list.map(([a, b]) => {
        const { dash } = style(b.nature, b.status);
        return Plot.link([a], {
          x1: () => a.value,
          x2: () => b.value,
          y1: y,
          y2: y,
          stroke: color(a),
          strokeWidth: tokens[focused(a) ? "stroke-width-focus" : "stroke-width-context"],
          strokeDasharray: dash ? tokens[dash] : null,
        });
      }),
      Plot.dot(
        list.map(([a]) => a),
        { x: "value", y, r: 3, fill: color, stroke: color },
      ),
      Plot.dot(
        list.map(([, b]) => b),
        {
          x: "value",
          y,
          r: 5,
          fill: (r) => (style(r.nature, r.status).hollow ? tokens["color-background"] : color(r)),
          stroke: color,
          strokeWidth: tokens["stroke-width-context"],
        },
      ),
      ...focus.map((r, i) => Plot.text([r], { x: "value", y, text: () => periods[i], dy: -10, fill: tokens["color-text-muted"] })),
    ],
  });
}

/** Each area from its first to its second value, focus first (the line chart's wording). */
function describe(rows, s) {
  pairs(rows);
  return seriesAlt(rows, s);
}

export const dumbbell = compose(draw, describe);
