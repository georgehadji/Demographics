import assert from "node:assert/strict";
import { test } from "node:test";
import { formatNumber } from "../src/format.js";

test("Greek grouping and decimal comma (PROPOSAL §7A examples)", () => {
  assert.equal(formatNumber(10372335), "10.372.335");
  assert.equal(formatNumber(-0.0003, { style: "percent", minimumFractionDigits: 2 }), "−0,03%");
  assert.equal(formatNumber(1.5, { minimumFractionDigits: 1 }), "1,5");
});

test("English grouping", () => {
  assert.equal(formatNumber(10372335, {}, "en"), "10,372,335");
  assert.equal(formatNumber(-1234.5, {}, "en"), "−1,234.5");
});

test("negative numbers always use the true minus sign", () => {
  for (const locale of ["el-GR", "en"])
    for (const options of [{}, { style: "percent" }, { signDisplay: "exceptZero" }]) {
      const text = formatNumber(-12.5, options, locale);
      assert.ok(text.startsWith("−") && !text.includes("-"), `${locale} ${text}`);
    }
  assert.equal(formatNumber(2.5, { signDisplay: "exceptZero" }), "+2,5");
});
