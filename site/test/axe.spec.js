// No WCAG 2.2 A/AA violation found by axe on one page of each kind, in light and dark mode
// (Build workflow, after the render).
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SITE = new URL("../_site/", import.meta.url);
// Tab presses allowed to reach a control: the navbar and the page's links come first.
const MAX_TABS = 80;
const PAGES = ["index.html", "indicators/index.html", "indicators/total_fertility_rate.html", "regions/index.html", "regions/EL30.html", "projections.html", "definitions.html", "sources.html", "ai.html", "errata.html"];

// The tooltips are SVG titles, shown under the pointer; the keyboard reaches the same
// fields through the source panel and the data table, both details elements.
test("the keyboard opens a chart's data table and source panel", async ({ page }) => {
  await page.goto(new URL("indicators/total_fertility_rate.html", SITE).href);
  for (const name of ["Πίνακας δεδομένων", "Πηγή και ορισμός"]) {
    const summary = page.locator("summary", { hasText: name }).first();
    for (let i = 0; i < MAX_TABS && !(await summary.evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
    await expect(summary).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(summary.locator("xpath=..")).toHaveAttribute("open", "");
  }
});

for (const scheme of ["light", "dark"])
  for (const page of PAGES)
    test(`${page} in ${scheme}: no accessibility violations`, async ({ page: p }) => {
      await p.emulateMedia({ colorScheme: scheme });
      await p.goto(new URL(page, SITE).href);
      await p.locator("details").evaluateAll((all) => all.forEach((d) => (d.open = true)));
      const { violations } = await new AxeBuilder({ page: p })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
    });
