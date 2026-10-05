// Decomposition with an explicit sum (PROPOSAL §7A; R1): the parts of one area's total in
// one period as floating bars, each starting where the one before ended, then the total
// from zero. Parts and total are definition_ids (spec.parts in order, spec.total); the
// chart fails unless the parts add up to the total within spec.tolerance (default 0). One
// area, so one colour: position and labels tell parts and total apart, the grammar styles
// each bar.
import * as Plot from "@observablehq/plot";
import { barLook, compose, frame, natureNote, sentence, tip, unique } from "./chart.js";

// Pixels kept free above and below the bars for their value labels.
const VALUE_ROOM = 18;
// Room for signed tick labels such as "−125.000" (Plot's default, 40, cuts the sign).
const MARGIN_LEFT = 60;

/** The parts, each with where it starts and ends, and the total from zero. */
function steps(rows, s) {
  if (!s.parts?.length || !s.total) throw new Error("a waterfall needs spec.parts and spec.total (definition_ids)");
  for (const r of rows) if (r.interval || r.scenario_id) throw new Error("a waterfall draws central values, no scenarios");
  for (const key of ["geo_code", "period"])
    if (unique(rows, key).length !== 1) throw new Error(`a waterfall shows one ${key}, not ${unique(rows, key).join(", ")}`);
  const ids = [...s.parts, s.total];
  const extra = unique(rows, "definition_id").filter((id) => !ids.includes(id));
  if (extra.length) throw new Error(`rows that are neither a part nor the total: ${extra.join(", ")}`);
  const one = (id) => {
    const found = rows.filter((r) => r.definition_id === id);
    if (found.length !== 1 || found[0].value === null) throw new Error(`${id}: needs exactly one value`);
    return found[0];
  };
  let end = 0;
  const parts = s.parts.map((id) => {
    const row = one(id);
    const start = end;
    end += row.value;
    return { row, start, end };
  });
  const total = one(s.total);
  if (Math.abs(end - total.value) > (s.tolerance ?? 0))
    throw new Error(`the parts add up to ${end}, the total ${s.total} is ${total.value}`);
  return [...parts, { row: total, start: 0, end: total.value }];
}

function draw(rows, s, options) {
  const { tokens } = options;
  const list = steps(rows, s);
  const accent = tokens["color-accent"];
  const muted = tokens["color-text-muted"];
  const x = (d) => s.label(d.row.definition_id);
  return Plot.plot({
    ...frame(s, options),
    marginLeft: MARGIN_LEFT,
    x: { label: null, domain: list.map(x) },
    // room for the value labels beyond the highest and the lowest bar
    y: { label: s.unit, tickFormat: s.format, grid: true, insetTop: VALUE_ROOM, insetBottom: VALUE_ROOM },
    marks: [
      ...list.map((d) => Plot.barY([d], { x, y1: "start", y2: "end", ...barLook(d.row, accent, tokens), title: () => `${s.label(d.row.definition_id)} · ${tip(s, d.row)}` })),
      // connectors: each part's end to the next bar
      Plot.link(list.slice(0, -1), { x1: x, x2: (_, i) => x(list[i + 1]), y1: "end", y2: "end", stroke: muted, strokeWidth: tokens["stroke-width-band-edge"] }),
      Plot.ruleY([0], { stroke: tokens["color-text"], strokeWidth: tokens["stroke-width-band-edge"] }),
      // each value beyond its bar's end: above a rise, below a fall
      ...[
        [list.filter((d) => d.row.value >= 0), -6],
        [list.filter((d) => d.row.value < 0), 10],
      ].map(([data, dy]) => Plot.text(data, { x, y: (d) => (dy < 0 ? Math.max : Math.min)(d.start, d.end), text: (d) => s.format(d.row.value), dy, fill: tokens["color-text"] })),
    ],
  });
}

/** "Φυσική μεταβολή −55.386; καθαρή μετανάστευση 49.637; σύνολο: μεταβολή −5.749 (Ελλάδα 2025)." */
function describe(rows, s) {
  const list = steps(rows, s);
  const total = list.at(-1).row;
  const parts = list.slice(0, -1).map(({ row }) => `${s.label(row.definition_id)} ${s.format(row.value)}${natureNote(s, row)}`);
  parts.push(`${s.text.total}: ${s.label(total.definition_id)} ${s.format(total.value)}${natureNote(s, total)} (${s.label(total.geo_code)} ${total.period})`);
  return sentence(s, parts, rows);
}

export const waterfall = compose(draw, describe);
