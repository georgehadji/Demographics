// Maps of the Greek regions (PROPOSAL §7A). A choropleth shows rates only, with its
// classification named in the legend; proportional symbols show counts, and sit beside
// it because Attica holds over a third of the population in a small area. Geometry is
// the data product's geometry_el_nuts2.geojson (pipeline/src/grpop/parse/gisco.py),
// passed as spec.geometry; its attribution goes into the footer of every map, as the
// GISCO terms require. spec.focus is the region outlined in the accent.
import * as Plot from "@observablehq/plot";
import { compose, frame, natureNote, sentence, unique } from "./chart.js";
import { style } from "./grammar.js";

const CLASSES = ["quantize", "quantile"];
// A rate: "per 1000 …", "% of …", "… per woman", or years (ages, life expectancy).
// ponytail: decided from the unit's wording; move to a field of definitions.yaml if a
// unit ever reads ambiguously.
const RATE = /(^|\s)per\s|%|^years$/;
const MAX_RADIUS = 28;

/** Exterior rings clockwise and holes counter-clockwise, as d3's spherical geometry needs. */
function rewind(geometry) {
  const area = (ring) => ring.reduce((sum, [x1, y1], i) => {
    const [x2, y2] = ring[(i + 1) % ring.length];
    return sum + (x1 * y2 - x2 * y1);
  }, 0);
  const polygon = (rings) => rings.map((ring, i) => ((area(ring) > 0) === (i === 0) ? [...ring].reverse() : ring));
  const { type, coordinates } = geometry;
  if (type === "Polygon") return { type, coordinates: polygon(coordinates) };
  if (type === "MultiPolygon") return { type, coordinates: coordinates.map(polygon) };
  throw new Error(`unsupported geometry ${type}`);
}

/** The regions with their row (if any), after checking geometry and rows. */
function regions(rows, s) {
  const g = s.geometry;
  if (g?.type !== "FeatureCollection") throw new Error("a map needs spec.geometry, a GeoJSON FeatureCollection");
  if (!g.attribution) throw new Error("map geometry needs its attribution, shown on every map");
  if (rows.some((r) => r.interval)) throw new Error("a map draws central values only");
  if (unique(rows, "sex").length > 1 || unique(rows, "age").length > 1) throw new Error("a map shows one sex and age");
  const period = String(s.period ?? unique(rows, "period").sort().at(-1));
  const shown = rows.filter((r) => r.period === period && !r.scenario_id);
  const byGeo = new Map(shown.map((r) => [r.geo_code, r]));
  if (byGeo.size !== shown.length) throw new Error("one value per region");
  const codes = new Set(g.features.map((f) => f.id));
  const unknown = [...byGeo.keys()].filter((c) => !codes.has(c));
  if (unknown.length) throw new Error(`no geometry for ${unknown.join(", ")}`);
  return { period, features: g.features.map((f) => ({ ...f, geometry: rewind(f.geometry), row: byGeo.get(f.id) })) };
}

/** Base map, boundaries, focus outline and the grammar's marks shared by both map types. */
function base(features, s, tokens) {
  const geometry = { type: "FeatureCollection", features };
  const boundary = { stroke: tokens["color-boundary"], strokeWidth: tokens["stroke-width-boundary"] };
  const dashed = (f) => f.row && style(f.row.nature, "final").dash;
  return {
    projection: { type: "conic-equal-area", parallels: [35, 41], rotate: [-24, 0], domain: geometry },
    under: [Plot.geo(features, { fill: tokens["color-surface"], ...boundary })],
    over: [
      ...unique(features.filter(dashed).map((f) => ({ f, dash: dashed(f) })), "dash").map((dash) =>
        Plot.geo(features.filter((f) => dashed(f) === dash), { fill: "none", ...boundary, strokeDasharray: tokens[dash] }),
      ),
      Plot.geo(features.filter((f) => f.id === s.focus), { fill: "none", stroke: tokens["color-accent"], strokeWidth: tokens["stroke-width-focus"] }),
    ],
  };
}

const caption = (options, s) => `${options.caption} · ${s.geometry.attribution}`;

function drawChoropleth(rows, s, options) {
  const { tokens } = options;
  if (!rows.every((r) => RATE.test(r.unit))) throw new Error(`a choropleth shows rates only, not ${rows[0].unit}`);
  const classes = s.classes ?? "quantize";
  if (!CLASSES.includes(classes)) throw new Error(`unknown classification ${classes}`);
  const { features } = regions(rows, s);
  const { projection, under, over } = base(features, s, tokens);
  const valued = features.filter((f) => f.row?.value != null);
  const diverging = s.palette === "diverging";
  const extent = Math.max(...valued.map((f) => Math.abs(f.row.value)));
  const hollow = valued.filter((f) => style(f.row.nature, f.row.status).hollow);
  const digits = Math.max(0, ...valued.map((f) => (String(f.row.value).split(".")[1] ?? "").length));
  return Plot.plot({
    ...frame(s, { ...options, caption: caption(options, s) }),
    projection,
    color: {
      type: classes,
      range: tokens[diverging ? "palette-diverging" : "palette-sequential"],
      ...(diverging && classes === "quantize" ? { domain: [-extent, extent] } : {}),
      legend: true,
      label: `${s.unit} · ${s.text.classes[classes]}`,
      // class boundaries are computed: show them no finer than the data
      tickFormat: (v) => s.format(+v.toFixed(digits)),
    },
    marks: [
      ...under,
      Plot.geo(valued, { fill: (f) => f.row.value, stroke: tokens["color-boundary"], strokeWidth: tokens["stroke-width-boundary"] }),
      ...over,
      Plot.dot(hollow, Plot.centroid({ r: 3.5, fill: tokens["color-background"], stroke: tokens["color-text"] })),
    ],
  });
}

function drawSymbols(rows, s, options) {
  const { tokens } = options;
  if (rows.some((r) => RATE.test(r.unit))) throw new Error(`proportional symbols show counts, not ${rows[0].unit}`);
  const { features } = regions(rows, s);
  const { projection, under, over } = base(features, s, tokens);
  const valued = features.filter((f) => f.row?.value != null).sort((a, b) => b.row.value - a.row.value);
  const max = Math.max(...valued.map((f) => f.row.value));
  const radius = (v) => MAX_RADIUS * Math.sqrt(v / max);
  const color = (f) => (f.id === s.focus ? tokens["color-accent"] : tokens["color-comparator"]);
  const hollow = (f) => style(f.row.nature, f.row.status).hollow;
  const legend = [max, max / 4].map((v) => ({ v, r: radius(v) }));
  const muted = tokens["color-text-muted"];
  return Plot.plot({
    ...frame(s, { ...options, caption: caption(options, s) }),
    projection,
    // area proportional to the value; the key's constant radii are pixels, so they match
    r: { type: "sqrt", domain: [0, max], range: [0, MAX_RADIUS] },
    marginBottom: 2 * MAX_RADIUS + 16,
    marks: [
      ...under,
      ...over,
      // largest first, so smaller circles stay on top
      Plot.dot(
        valued,
        Plot.centroid({
          r: (f) => f.row.value,
          fill: (f) => (hollow(f) ? tokens["color-background"] : color(f)),
          stroke: (f) => (hollow(f) ? color(f) : tokens["color-background"]),
          strokeWidth: tokens["stroke-width-context"],
        }),
      ),
      // size key: nested circles in the bottom-left corner
      ...legend.map(({ r }) =>
        Plot.dot([0], { frameAnchor: "bottom-left", dx: MAX_RADIUS + 4, dy: MAX_RADIUS + 12 - r, r, fill: "none", stroke: muted }),
      ),
      ...legend.map(({ v, r }) =>
        Plot.text([s.format(v)], { frameAnchor: "bottom-left", dx: 2 * MAX_RADIUS + 12, dy: MAX_RADIUS + 12 - 2 * r, fill: muted, textAnchor: "start" }),
      ),
    ],
  });
}

/** The highest and lowest region, and the regions without a value. */
function describe(rows, s) {
  const { period, features } = regions(rows, s);
  const valued = features.filter((f) => f.row?.value != null);
  const name = (f) => s.label(f.id);
  const at = (f) => `${name(f)} ${s.format(f.row.value)}${natureNote(s, f.row)}`;
  const parts = [];
  if (valued.length) {
    const high = valued.reduce((a, b) => (b.row.value > a.row.value ? b : a));
    const low = valued.reduce((a, b) => (b.row.value < a.row.value ? b : a));
    parts.push(`${period}: ${s.text.highest} ${at(high)}`, `${s.text.lowest} ${at(low)}`);
  }
  const missing = features.filter((f) => f.row?.value == null);
  if (missing.length) parts.push(`${s.text.status.not_available}: ${missing.map(name).join(", ")}`);
  return sentence(s, parts, rows);
}

export const choropleth = compose(drawChoropleth, describe);
export const symbols = compose(drawSymbols, describe);
