import assert from "node:assert/strict";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";
import { build } from "../src/build.js";
import { MODES, resolve } from "../src/tokens.js";

const modes = resolve();
const dir = pathToFileURL(mkdtempSync(join(tmpdir(), "tokens-")) + "/");
build(dir);
const read = (name) => readFileSync(new URL(name, dir), "utf8");

test("every token is a CSS variable, with its dark and print values where they differ", () => {
  const css = read("tokens.css");
  for (const [name, value] of Object.entries(modes.light))
    for (const [i, v] of (Array.isArray(value) ? value : [value]).entries()) {
      const variable = Array.isArray(value) ? `--${name}-${i + 1}` : `--${name}`;
      assert.ok(css.includes(`${variable}: ${v};`), variable);
    }
  assert.ok(css.includes(`--color-accent: ${modes.dark["color-accent"]};`));
  assert.ok(css.includes(`--color-accent: ${modes.print["color-accent"]};`));
  assert.ok(css.includes('--font-stack: "Noto Sans", system-ui, sans-serif;'));
});

test("the JS module gives every token in every mode, colours as hex", async () => {
  const { tokens } = await import(new URL("tokens.js", dir));
  for (const mode of MODES) {
    assert.deepEqual(Object.keys(tokens[mode]), Object.keys(modes[mode]));
    assert.match(tokens[mode]["color-accent"], /^#[0-9a-f]{6}$/);
    assert.equal(tokens[mode]["palette-sequential"].length, modes[mode]["palette-sequential"].length);
  }
});

test("the brand files name a palette colour for each theme role", () => {
  for (const [file, mode] of [["_brand.yml", "light"], ["_brand-dark.yml", "dark"]]) {
    const brand = JSON.parse(read(file)); // YAML is a superset of JSON
    for (const role of ["background", "foreground", "primary"])
      assert.match(brand.color.palette[brand.color[role]], /^#[0-9a-f]{6}$/, `${file} ${role}`);
    assert.equal(brand.color.palette.accent.length, 7);
    assert.equal(brand.typography.base.family, modes[mode]["font-family"]);
  }
});
