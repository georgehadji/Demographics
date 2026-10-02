// Shared by the chart tests: a DOM, the tokens and a hand-written observation row (not
// data). node --test also loads this file as a test file; it defines no tests.
import { after } from "node:test";
import { JSDOM } from "jsdom";
import { hexTokens } from "../../design/src/build.js";

const { window } = new JSDOM("");
export const { document } = window;
after(() => window.close()); // an open window keeps the test process alive
export const MODES = hexTokens();
export const tokens = MODES.light;

export const row = (geo_code, period, value, extra = {}) => ({
  geo_code,
  period,
  sex: "total",
  age: "total",
  value,
  unit: "persons",
  nature: "observed",
  status: "final",
  break_in_series: false,
  scenario_id: null,
  interval: null,
  source: "eurostat",
  dataset_code: "demo_gind",
  vintage: "2026-09-15",
  ...extra,
});

/** Mark groups by kind (Plot's aria-label, kept as data-mark); a mark's constant styles sit on its group. */
export const marks = (fig, kind) => [...fig.querySelectorAll(`g[data-mark="${kind}"]`)];

/** A mark attribute, on its group or, for clipped or faceted marks, one group deeper. */
export const attr = (g, name) => g.getAttribute(name) ?? g.querySelector(`[${name}]`)?.getAttribute(name) ?? null;
