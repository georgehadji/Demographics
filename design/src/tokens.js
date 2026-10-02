// Reads tokens.json and resolves it per mode: {light, dark, print} -> flat {name: value}.
import { readFileSync } from "node:fs";

export const MODES = ["light", "dark", "print"];
const SOURCE = new URL("../tokens.json", import.meta.url);

const isModeMap = (v) =>
  v && typeof v === "object" && !Array.isArray(v) && "light" in v &&
  Object.keys(v).every((k) => MODES.includes(k));

/** {light: {"color-accent": "oklch(...)", "palette-sequential": [...], ...}, dark: ..., print: ...} */
export function resolve(tokens = JSON.parse(readFileSync(SOURCE, "utf8"))) {
  const out = Object.fromEntries(MODES.map((m) => [m, {}]));
  const walk = (node, path) => {
    for (const [key, value] of Object.entries(node)) {
      if (key.startsWith("$")) continue;
      const name = [...path, key].join("-");
      if (isModeMap(value)) {
        for (const mode of MODES) out[mode][name] = value[mode] ?? value.light;
      } else if (value && typeof value === "object" && !Array.isArray(value)) {
        walk(value, [...path, key]);
      } else {
        for (const mode of MODES) out[mode][name] = value;
      }
    }
  };
  walk(tokens, []);
  return out;
}
