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

const colors = (flat) =>
  Object.entries(flat).flatMap(([k, v]) =>
    (Array.isArray(v) ? v : [v]).filter((c) => typeof c === "string" && c.startsWith("oklch(")).map((c) => [k, c]),
  );

for (const mode of MODES) {
  const t = modes[mode];

  test(`${mode}: every colour is OKLCH inside the sRGB gamut`, () => {
    for (const [name, c] of colors(t)) assert.ok(displayable(c), `${name} ${c}`);
  });

  test(`${mode}: text has AA contrast (4.5:1) on background and surface`, () => {
    for (const fg of ["color-text", "color-text-muted"])
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
