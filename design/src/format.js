// The one number formatter (PROPOSAL §7A): locale grouping and decimals through
// Intl.NumberFormat, and always the true minus sign (U+2212), which Intl does not use
// for el-GR or en.
const MINUS = "−";

export function formatNumber(value, options = {}, locale = "el-GR") {
  return new Intl.NumberFormat(locale, options)
    .formatToParts(value)
    .map((part) => (part.type === "minusSign" ? MINUS : part.value))
    .join("");
}
