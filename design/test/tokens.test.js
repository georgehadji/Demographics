// Validators for tokens.json: sRGB gamut, WCAG 2.2 AA contrast in every mode, and
// colours that stay distinct under protan, deutan and tritan simulation (PROPOSAL §7A).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  differenceEuclidean,
  displayable,
  filterDeficiencyDeuter,
  filterDeficiencyProt,
  filterDeficiencyTrit,
  formatHex,
  interpolate,
  oklch,
  wcagContrast,
} from "culori";
import { MODES, resolve } from "../src/tokens.js";

const modes = resolve();
const deltaE = differenceEuclidean("oklab");
// Machado et al. (2009) simulations at full severity, and normal vision.
const VISION = {
  normal: (c) => c,
  protan: filterDeficiencyProt(1),
  deutan: filterDeficiencyDeuter(1),
  tritan: filterDeficiencyTrit(1),
};
// Contrast is measured on the hex colour that is rendered, not the exact OKLCH value.
const contrast = (a, b) => wcagContrast(formatHex(a), formatHex(b));
const MIN_DISTANCE = 0.08; // OKLab ΔE; about four times a just-noticeable difference
const MIN_LIGHTNESS_GAP = 0.08; // OKLCH L; for grayscale print and achromatopsia

const colors = (flat) =>
  Object.entries(flat).flatMap(([k, v]) =>
    (Array.isArray(v) ? v : [v]).filter((c) => typeof c === "string" && c.startsWith("oklch(")).map((c) => [k, c]),
  );

for (const mode of MODES) {
  const t = modes[mode];

  test(`${mode}: every colour is OKLCH inside the sRGB gamut`, () => {
    for (const [name, c] of colors(t)) assert.ok(displayable(c), `${name} ${c}`);
  });

  test(`${mode}: text and line labels have AA contrast (4.5:1) on background and surface`, () => {
    // Charts label the focus and scenario lines in the line's colour (charts/src/line.js).
    for (const fg of ["color-text", "color-text-muted", "color-accent", "color-scenario"])
      for (const bg of ["color-background", "color-surface"])
        assert.ok(contrast(t[fg], t[bg]) >= 4.5, `${fg} on ${bg}: ${contrast(t[fg], t[bg])}`);
  });

  test(`${mode}: data marks have non-text contrast (3:1) on background and surface`, () => {
    for (const fg of ["color-accent", "color-comparator", "color-scenario"])
      for (const bg of ["color-background", "color-surface"])
        assert.ok(contrast(t[fg], t[bg]) >= 3, `${fg} on ${bg}: ${contrast(t[fg], t[bg])}`);
  });

  test(`${mode}: the accent stands apart from comparators and scenarios in every vision`, () => {
    for (const other of ["color-comparator", "color-scenario"])
      for (const [vision, sim] of Object.entries(VISION)) {
        const d = deltaE(sim(t["color-accent"]), sim(t[other]));
        assert.ok(d >= MIN_DISTANCE, `accent vs ${other}, ${vision}: ${d}`);
      }
  });

  test(`${mode}: scenarios use another hue family than the accent`, () => {
    const gap = Math.abs(oklch(t["color-accent"]).h - oklch(t["color-scenario"]).h) % 360;
    assert.ok(Math.min(gap, 360 - gap) >= 90, `hue gap ${gap}`);
  });

  test(`${mode}: accent, comparator and scenario differ in lightness, so they hold in grayscale`, () => {
    const names = ["color-accent", "color-comparator", "color-scenario"];
    for (const [i, a] of names.entries())
      for (const b of names.slice(i + 1)) {
        const gap = Math.abs(oklch(t[a]).l - oklch(t[b]).l);
        assert.ok(gap >= MIN_LIGHTNESS_GAP, `${a} vs ${b}: ΔL ${gap}`);
      }
  });

  test(`${mode}: no map class can be mistaken for the accent`, () => {
    for (const p of ["palette-sequential", "palette-diverging"])
      for (const c of t[p]) {
        const d = deltaE(c, t["color-accent"]);
        assert.ok(d >= MIN_DISTANCE, `${p} ${c}: ${d}`);
      }
  });

  test(`${mode}: uncertainty bands stay visible and ordered`, () => {
    const band = (k) => interpolate([t["color-background"], t["color-accent"]], "rgb")(t[k]);
    const inner = contrast(band("opacity-band-80"), t["color-background"]);
    const outer = contrast(band("opacity-band-95"), t["color-background"]);
    assert.ok(outer >= 1.3, `95% band: ${outer}`);
    assert.ok(inner >= 1.6 && inner > outer, `80% band: ${inner}`);
    assert.ok(t["stroke-width-band-edge"] > 0, "bands have an edge line in the accent colour");
  });

  test(`${mode}: region boundaries have 3:1 where a map class alone does not`, () => {
    const bg = t["color-background"];
    const faint = [...t["palette-sequential"], ...t["palette-diverging"]].filter((c) => contrast(c, bg) < 3);
    for (const c of [bg, t["color-surface"], ...faint]) {
      const r = contrast(t["color-boundary"], c);
      assert.ok(r >= 3, `boundary on ${c}: ${r}`);
    }
  });

  test(`${mode}: sequential palette is monotone in lightness and distinct step by step`, () => {
    const p = t["palette-sequential"];
    assertMonotone(p.map((c) => oklch(c).l));
    assertAdjacentDistinct(p);
  });

  test(`${mode}: diverging palette has a neutral centre, symmetric arms and distinct steps`, () => {
    const p = t["palette-diverging"];
    const mid = (p.length - 1) / 2;
    assert.ok(Number.isInteger(mid), "odd number of classes");
    assert.ok(oklch(p[mid]).c < 0.01, "neutral centre");
    const l = p.map((c) => oklch(c).l);
    assertMonotone(l.slice(0, mid + 1));
    assertMonotone(l.slice(mid));
    for (let i = 1; i <= mid; i++) {
      assert.ok(Math.abs(l[mid - i] - l[mid + i]) < 0.01, `lightness of arm step ${i}`);
      for (const [vision, sim] of Object.entries(VISION)) {
        const d = deltaE(sim(p[mid - i]), sim(p[mid + i]));
        assert.ok(d >= MIN_DISTANCE, `arms at step ${i}, ${vision}: ${d}`);
      }
    }
    assertAdjacentDistinct(p);
  });
}

function assertMonotone(values) {
  const up = values.slice(1).every((v, i) => v > values[i]);
  const down = values.slice(1).every((v, i) => v < values[i]);
  assert.ok(up || down, `not monotone: ${values}`);
}

function assertAdjacentDistinct(palette) {
  for (const [vision, sim] of Object.entries(VISION))
    for (let i = 1; i < palette.length; i++) {
      const d = deltaE(sim(palette[i - 1]), sim(palette[i]));
      assert.ok(d >= MIN_DISTANCE, `steps ${i}-${i + 1}, ${vision}: ${d}`);
    }
}
