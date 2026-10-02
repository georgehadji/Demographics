// Generates dist/ from tokens.json (ADR 0006: derived files are generated, never edited):
// tokens.css (CSS variables in OKLCH), tokens.js (per-mode hex values for scales) and
// Quarto's _brand.yml / _brand-dark.yml.
import { mkdirSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { formatHex } from "culori";
import { MODES, resolve } from "./tokens.js";

const isColor = (v) => typeof v === "string" && v.startsWith("oklch(");
const hex = (v) => (Array.isArray(v) ? v.map(hex) : isColor(v) ? formatHex(v) : v);

function cssVars(flat) {
  return Object.entries(flat).flatMap(([name, value]) =>
    Array.isArray(value)
      ? value.map((v, i) => `  --${name}-${i + 1}: ${v};`)
      : [`  --${name}: ${value};`],
  );
}

export function css(modes = resolve()) {
  const { light } = modes;
  const font = `"${light["font-family"]}", ${light["font-fallback"]}`;
  const changed = (mode) =>
    Object.fromEntries(
      Object.entries(modes[mode]).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(light[k])),
    );
  const block = (selector, flat, pad = "") =>
    `${pad}${selector} {\n${cssVars(flat).map((line) => pad + line).join("\n")}\n${pad}}`;
  const dark = changed("dark");
  return [
    "/* Generated from design/tokens.json by src/build.js. Do not edit. */",
    block(":root", { ...light, "font-stack": font }),
    `@media (prefers-color-scheme: dark) {\n${block(':root:not([data-theme="light"])', dark, "  ")}\n}`,
    block(':root[data-theme="dark"]', dark),
    `@media print {\n${block(":root", changed("print"), "  ")}\n}`,
    "",
  ].join("\n\n");
}

/** Per-mode tokens with colours as hex, the form chart scales take. */
export function hexTokens(modes = resolve()) {
  return Object.fromEntries(
    MODES.map((m) => [m, Object.fromEntries(Object.entries(modes[m]).map(([k, v]) => [k, hex(v)]))]),
  );
}

export function js(modes = resolve()) {
  return (
    "// Generated from design/tokens.json by src/build.js. Do not edit.\n" +
    `export const tokens = ${JSON.stringify(hexTokens(modes), null, 2)};\n`
  );
}

// YAML is a superset of JSON, so the brand files are written as JSON.
export function brand(mode, modes = resolve()) {
  const flat = modes[mode];
  const colors = Object.fromEntries(
    Object.entries(flat)
      .filter(([k, v]) => k.startsWith("color-") && isColor(v))
      .map(([k, v]) => [k.slice("color-".length), hex(v)]),
  );
  const family = flat["font-family"];
  return JSON.stringify(
    {
      color: {
        palette: colors,
        background: "background",
        foreground: "text",
        primary: "accent",
      },
      typography: {
        fonts: [{ family, source: "google" }],
        base: { family },
        headings: { family },
      },
    },
    null,
    2,
  ) + "\n";
}

export function build(dir = new URL("../dist/", import.meta.url)) {
  mkdirSync(dir, { recursive: true });
  writeFileSync(new URL("tokens.css", dir), css());
  writeFileSync(new URL("tokens.js", dir), js());
  writeFileSync(new URL("_brand.yml", dir), brand("light"));
  writeFileSync(new URL("_brand-dark.yml", dir), brand("dark"));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) build();
