// Population pyramid (PROPOSAL §7A): men to the left, women to the right, one bar per
// age, the oldest at the top. A second profile (another year or area) is drawn as an
// outline over the same pyramid, never as a second pyramid beside it. The main profile
// is the focus area at spec.period (default: its latest period); the grammar styles its
// bars (projected bars are lighter with a dashed edge, provisional ones hollow).
import * as Plot from "@observablehq/plot";
import { ageStart, barLook, compose, frame, natureNote, sentence, tip, unique } from "./chart.js";
import { style } from "./grammar.js";

const SIDE = { male: -1, female: 1 };
// More ages than this and only every tenth is labelled on the axis.
const MAX_AGE_TICKS = 25;

const profileKey = (r) => `${r.geo_code}|${r.period}|${r.scenario_id ?? ""}`;

/** The main profile and the optional comparison, each a list of rows. */
function profiles(rows, s) {
  for (const r of rows) {
    if (!(r.sex in SIDE)) throw new Error(`a pyramid needs male and female rows, not ${r.sex}`);
    if (ageStart(r.age) === null) throw new Error(`a pyramid needs ages, not ${r.age}`);
    if (r.interval) throw new Error("a pyramid draws central values only");
    if (r.value === null) throw new Error(`a pyramid needs every age: ${r.geo_code} ${r.period} ${r.sex} ${r.age} is not available`);
  }
  const period = String(s.period ?? unique(rows.filter((r) => r.geo_code === s.focus && !r.scenario_id), "period").sort().at(-1));
  const groups = Map.groupBy(rows, profileKey);
  const main = [...groups.values()].find((g) => g[0].geo_code === s.focus && g[0].period === period && !g[0].scenario_id);
  if (!main) throw new Error(`no rows for ${s.focus} in ${period}`);
  const others = [...groups.values()].filter((g) => g !== main);
  if (others.length > 1) throw new Error(`a pyramid compares two profiles, not ${groups.size}`);
  return [main, others[0] ?? []];
}

const name = (s, r) => `${s.label(r.geo_code)} ${r.period}` + (r.scenario_id ? ` (${s.label(r.scenario_id)})` : "");
const signed = (r) => SIDE[r.sex] * r.value;

function draw(rows, s, options) {
  const { tokens } = options;
  const [main, compare] = profiles(rows, s);
  const ages = unique(rows, "age").sort((a, b) => ageStart(b) - ageStart(a));
  const accent = tokens["color-accent"];
  const marks = [];
  for (const group of Map.groupBy(main, (r) => `${r.nature}|${r.status}`).values()) {
    const look = style(group[0].nature, group[0].status);
    if (!look.drawn) continue;
    const color = tokens[look.color] ?? accent;
    marks.push(
      Plot.barX(group, {
        x: signed,
        y: "age",
        ...barLook(group[0], color, tokens),
        insetTop: 0.5,
        insetBottom: 0.5,
        title: (r) => `${tip(s, r)} · ${s.text.sex[r.sex]}, ${s.text.age} ${r.age}`,
      }),
    );
  }
  if (compare.length)
    marks.push(
      Plot.barX(compare, { x: signed, y: "age", fill: "none", stroke: tokens["color-comparator"], strokeWidth: tokens["stroke-width-context"], title: (r) => `${tip(s, r)} · ${s.text.sex[r.sex]}, ${s.text.age} ${r.age}` }),
    );
  const muted = tokens["color-text-muted"];
  marks.push(
    Plot.ruleX([0], { stroke: tokens["color-text"], strokeWidth: tokens["stroke-width-band-edge"] }),
    Plot.text([s.text.sex.male], { frameAnchor: "top-left", dy: -30, fill: muted }),
    Plot.text([s.text.sex.female], { frameAnchor: "top-right", dy: -30, fill: muted }),
    Plot.text([name(s, main[0])], { frameAnchor: "top", dy: -30, fill: accent }),
  );
  if (compare.length)
    marks.push(Plot.text([`${name(s, compare[0])} (${s.text.outline})`], { frameAnchor: "top", dy: -16, fill: muted }));
  return Plot.plot({
    ...frame(s, options),
    marginTop: 44,
    x: { label: s.unit, tickFormat: (v) => s.format(Math.abs(v)) },
    y: {
      label: null, // the ticks are ages
      domain: ages,
      ticks: ages.length > MAX_AGE_TICKS ? ages.filter((a) => ageStart(a) % 10 === 0) : ages,
    },
    marks,
  });
}

/** Per profile: men and women in all, and the largest age group, e.g. "Ελλάδα 2024: άνδρες …". */
function describe(rows, s) {
  const [main, compare] = profiles(rows, s);
  const parts = [main, compare]
    .filter((p) => p.length)
    .map((p) => {
      const total = (sex) => p.filter((r) => r.sex === sex).reduce((sum, r) => sum + r.value, 0);
      const byAge = [...Map.groupBy(p, (r) => r.age)].map(([age, g]) => [age, g.reduce((sum, r) => sum + r.value, 0)]);
      const [age] = byAge.reduce((a, b) => (b[1] > a[1] ? b : a));
      return `${name(s, p[0])}${natureNote(s, p[0])}: ${s.text.sex.male} ${s.format(total("male"))}, ${s.text.sex.female} ${s.format(total("female"))}, ${s.text.largest} ${age}`;
    });
  return sentence(s, parts, rows);
}

export const pyramid = compose(draw, describe);
