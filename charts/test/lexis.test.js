// The Lexis surface: cells, palette classes, cohort lines, provisional outline. Hand-written rows.
import assert from "node:assert/strict";
import { test } from "node:test";
import { lexis } from "../src/lexis.js";
import { attr, document, marks, row, tokens } from "./rows.js";

const ROWS = [];
for (let year = 2000; year <= 2009; year++)
  for (let age = 15; age <= 49; age++)
    ROWS.push(
      row("EL", String(year), Math.round(100 * Math.exp(-(((age - 30) / 6) ** 2))) / 1000, {
        age: String(age),
        unit: "births per woman",
        ...(year === 2009 ? { status: "provisional" } : {}),
      }),
    );
const SPEC = { title: "Η γονιμότητα μετατοπίζεται σε μεγαλύτερες ηλικίες", labels: { EL: "Ελλάδα" } };
const chart = (rows = ROWS, spec = SPEC) => lexis(rows, spec, { tokens, document });

test("one cell per value, filled from the sequential palette", () => {
  const [cellsGroup] = marks(chart().figure, "rect");
  const fills = new Set([...cellsGroup.querySelectorAll("rect")].map((r) => r.getAttribute("fill")));
  assert.equal(cellsGroup.querySelectorAll("rect").length, ROWS.length);
  for (const f of fills) assert.ok(tokens["palette-sequential"].includes(f), f);
  assert.ok(fills.size > 3, "several classes in use");
});

test("the diverging palette is centred on zero", () => {
  const rows = ROWS.map((r) => ({ ...r, value: r.value - 0.05 }));
  const [cellsGroup] = marks(chart(rows, { ...SPEC, palette: "diverging" }).figure, "rect");
  const fills = new Set([...cellsGroup.querySelectorAll("rect")].map((r) => r.getAttribute("fill")));
  for (const f of fills) assert.ok(tokens["palette-diverging"].includes(f), f);
});

test("cohort lines run diagonally every ten birth years", () => {
  const lines = marks(chart().figure, "line");
  assert.ok(lines.length >= 3);
  for (const g of lines) assert.equal(attr(g, "stroke"), tokens["color-boundary"]);
});

test("provisional cells are outlined, projections marked by a rule", () => {
  const [, outlined] = marks(chart().figure, "rect");
  assert.equal(outlined.querySelectorAll("rect").length, 35, "the 2009 column");
  assert.equal(marks(chart().figure, "rule").length, 0);
  const projected = ROWS.map((r) => (r.period >= "2008" ? { ...r, nature: "projected" } : r));
  assert.equal(marks(chart(projected).figure, "rule").length, 1);
});

test("the legend names the unit and the classification", () => {
  assert.ok(chart().figure.textContent.includes("births per woman · ίσα διαστήματα"));
  assert.ok(chart(ROWS, { ...SPEC, classes: "quantile" }).figure.textContent.includes("· ποσοστημόρια"));
});

test("alt text gives the highest and lowest value with age and year", () => {
  const { alt } = chart();
  assert.match(alt, /^Η γονιμότητα μετατοπίζεται σε μεγαλύτερες ηλικίες\. Ελλάδα: υψηλότερη τιμή 0,1 \(ηλικία 30, 2000\); χαμηλότερη τιμή 0 /);
  assert.ok(alt.endsWith("προσωρινές τιμές: 2009."));
});

test("a Lexis surface refuses age bands, months and several areas", () => {
  assert.throws(() => chart([row("EL", "2000", 1, { age: "15-19" })]), /single years of age/);
  assert.throws(() => chart([row("EL", "2000", 1, { age: "85+" })]), /single years of age/);
  assert.throws(() => chart([row("EL", "2000-01", 1, { age: "15" })]), /calendar years/);
  assert.throws(() => chart([row("EL", "2000", 1, { age: "15" }), row("PT", "2000", 1, { age: "15" })]), /one area/);
  assert.throws(() => chart(ROWS, { ...SPEC, classes: "jenks" }), /unknown classification/);
});

test("alt text says when the highest or lowest value is projected", () => {
  const projected = ROWS.map((r) => (r.period === "2000" ? { ...r, nature: "projected" } : r));
  assert.match(chart(projected).alt, /υψηλότερη τιμή 0,1 \(ηλικία 30, 2000, προβολή\)/);
});
