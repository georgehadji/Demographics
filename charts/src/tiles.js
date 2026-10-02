// Tile-grid small multiples (PROPOSAL §7A): one small line chart per region, placed on
// a grid that recalls the map (spec.layout, rows of data/reference/el_nuts2_tiles.csv:
// geo_code, row, col). Each tile shows its region in the accent over the focus area
// (spec.focus, e.g. the country) as a thin neutral reference line, on shared scales.
import * as Plot from "@observablehq/plot";
import { compose, frame, seriesAlt, seriesKey, unique } from "./chart.js";
import { seriesMarks } from "./line.js";
import { style } from "./grammar.js";

const TILE_WIDTH = 170;
const TILE_HEIGHT = 120;

function positions(rows, s) {
  if (!Array.isArray(s.layout)) throw new Error("tiles need spec.layout: rows of geo_code, row, col");
  if (rows.some((r) => r.interval)) throw new Error("tiles draw central values only");
  const at = new Map(s.layout.map((t) => [t.geo_code, { row: +t.row, col: +t.col }]));
  const cells = [...at.values()].map((p) => `${p.row},${p.col}`);
  if (new Set(cells).size !== cells.length) throw new Error("two tiles share a cell");
  const missing = unique(rows, "geo_code").filter((g) => g !== s.focus && !at.has(g));
  if (missing.length) throw new Error(`no tile for ${missing.join(", ")}`);
  return at;
}

function draw(rows, s, options) {
  const { tokens } = options;
  const at = positions(rows, s);
  const reference = rows.filter((r) => r.geo_code === s.focus && !r.scenario_id);
  const regions = unique(rows, "geo_code").filter((g) => g !== s.focus);
  const marks = [];
  for (const geo of regions) {
    const tile = at.get(geo);
    const facet = { fx: () => tile.col, fy: () => tile.row };
    const context = { width: tokens["stroke-width-context"], tokens, facet };
    // the tile's region is its focus; the reference runs through its breaks
    marks.push(...seriesMarks(reference, rows, { ...context, color: () => tokens["color-comparator"], gaps: false }));
    for (const part of Map.groupBy(rows.filter((r) => r.geo_code === geo), seriesKey).values()) {
      const color = (nature) => tokens[style(nature, "final").color] ?? tokens["color-accent"];
      marks.push(...seriesMarks(part, rows, { ...context, width: tokens["stroke-width-focus"], color }));
    }
    marks.push(
      // above the tile, where no line can run
      Plot.text([s.label(geo)], { fx: () => tile.col, fy: () => tile.row, frameAnchor: "top-left", dy: -9, fill: tokens["color-text"] }),
    );
  }
  marks.push(
    Plot.text([`${s.text.reference}: ${s.label(s.focus)}`], { facet: "super", frameAnchor: "top-right", dy: -34, fill: tokens["color-text-muted"] }),
  );
  const tiles = [...at.values()];
  const range = (k) => [...new Array(Math.max(...tiles.map((t) => t[k])) + 1).keys()];
  return Plot.plot({
    ...frame(s, options),
    width: range("col").length * TILE_WIDTH,
    height: range("row").length * TILE_HEIGHT + 60,
    marginTop: 46,
    fx: { domain: range("col"), axis: null, padding: 0.22 },
    fy: { domain: range("row"), axis: null, padding: 0.3 },
    x: { type: "utc", label: null, ticks: 2 },
    y: { label: s.unit, tickFormat: s.format, ticks: 3, grid: true },
    marks: [Plot.frame({ stroke: tokens["color-gridline"] }), ...marks],
  });
}

// Regions first, the reference area last.
export const tiles = compose(draw, (rows, s) => seriesAlt(rows, s, { focusFirst: false }));
