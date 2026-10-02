// Tile-grid small multiples: layout, reference line, labels. Hand-written rows.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { tiles } from "../src/tiles.js";
import { attr, document, marks, row, tokens } from "./rows.js";

const csvRows = (path) => {
  const [head, ...lines] = readFileSync(new URL(path, import.meta.url), "utf8").trim().split(/\r?\n/);
  const keys = head.split(",");
  return lines.map((l) => Object.fromEntries(l.split(",").map((v, i) => [keys[i], v])));
};
const LAYOUT = csvRows("../../data/reference/el_nuts2_tiles.csv");
const NUTS2 = csvRows("../../data/reference/nuts2024_el.csv")
  .map((r) => r.geo_code)
  .filter((g) => /^EL\d\d$/.test(g));

const REGIONS = ["EL30", "EL43", "EL52"];
const ROWS = ["EL", ...REGIONS].flatMap((geo, i) =>
  ["2014", "2019", "2024"].map((p, j) => row(geo, p, 100 - i * 5 - j, p === "2024" ? { status: "provisional" } : {})),
);
const SPEC = { title: "Όλες οι περιφέρειες χάνουν πληθυσμό", labels: { EL: "Ελλάδα", EL30: "Αττική", EL43: "Κρήτη", EL52: "Κεντρική Μακεδονία" }, layout: LAYOUT };
const chart = (rows = ROWS, spec = SPEC) => tiles(rows, spec, { tokens, document });

test("the layout places every Greek NUTS 2 region exactly once, each in its own cell", () => {
  assert.deepEqual(LAYOUT.map((t) => t.geo_code).sort(), NUTS2.sort());
  assert.equal(new Set(LAYOUT.map((t) => `${t.row},${t.col}`)).size, LAYOUT.length);
});

test("each region's tile holds its line in the accent over the reference line", () => {
  const groups = marks(chart().figure, "line");
  const strokes = groups.map((g) => attr(g, "stroke"));
  assert.equal(strokes.filter((c) => c === tokens["color-accent"]).length, REGIONS.length);
  assert.equal(strokes.filter((c) => c === tokens["color-comparator"]).length, REGIONS.length);
});

test("each tile is labelled with its region, and the reference is named once", () => {
  const texts = marks(chart().figure, "text").map((g) => g.textContent);
  for (const r of REGIONS) assert.ok(texts.includes(SPEC.labels[r]), r);
  assert.equal(texts.filter((t) => t === "λεπτή γραμμή: Ελλάδα").length, 1);
});

test("provisional values get hollow markers in every tile, the reference's too", () => {
  assert.equal(marks(chart().figure, "dot").length, 2 * REGIONS.length);
});

test("alt text lists the regions, then the reference", () => {
  const { alt } = chart();
  assert.ok(alt.startsWith("Όλες οι περιφέρειες χάνουν πληθυσμό. Αττική: από 95 (2014) σε 93 (2024)"), alt);
  assert.ok(alt.includes("; Ελλάδα: από 100 (2014) σε 98 (2024); προσωρινές τιμές: 2024."), alt);
});

test("tiles refuse a missing layout, an unplaced region and a shared cell", () => {
  assert.throws(() => chart(ROWS, { ...SPEC, layout: undefined }), /spec.layout/);
  assert.throws(() => chart([...ROWS, row("EL99", "2014", 1)]), /no tile for EL99/);
  assert.throws(() => chart(ROWS, { ...SPEC, layout: [...LAYOUT, { geo_code: "X", row: 0, col: 1 }] }), /share a cell/);
  assert.throws(() => chart([...ROWS, row("EL30", "2024", 90, { interval: "95_lower" })]), /central values only/);
});

test("a break in series is marked in its tile", () => {
  const rows = ROWS.map((r) => (r.geo_code === "EL43" && r.period === "2019" ? { ...r, break_in_series: true } : r));
  assert.ok(marks(chart(rows).figure, "text").some((g) => g.textContent === "*"));
});
