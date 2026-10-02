// The epistemic grammar (PROPOSAL §7A): one pure function from a value's nature and
// status to how it is drawn. It returns token names, not values, so it holds in every
// mode. The vocabularies are defined in pipeline/src/grpop/provenance.py;
// test/grammar.test.js fails when they drift apart.

const NATURE = {
  observed: { dash: null, band: false, color: null },
  official_estimate: { dash: null, band: false, color: null },
  derived: { dash: null, band: false, color: null },
  projected: { dash: "stroke-dash-projected", band: true, color: null },
  // Scenarios take another hue family than the series they belong to.
  scenario: { dash: "stroke-dash-scenario", band: false, color: "color-scenario" },
};

const STATUS = {
  final: { drawn: true, hollow: false },
  revised: { drawn: true, hollow: false },
  provisional: { drawn: true, hollow: true },
  not_available: { drawn: false, hollow: false },
};

/**
 * @returns {{dash: string|null, band: boolean, color: string|null, drawn: boolean, hollow: boolean}}
 *   dash: token of the line's dash pattern (null = solid); band: draw uncertainty bands;
 *   color: token that replaces the series colour (null = keep it); drawn: the value has
 *   a mark (not_available leaves a gap); hollow: hollow marker at the point.
 */
export function style(nature, status) {
  if (!Object.hasOwn(NATURE, nature)) throw new Error(`unknown nature: ${nature}`);
  if (!Object.hasOwn(STATUS, status)) throw new Error(`unknown status: ${status}`);
  return Object.freeze({ ...NATURE[nature], ...STATUS[status] });
}

export const NATURES = Object.keys(NATURE);
export const STATUSES = Object.keys(STATUS);
