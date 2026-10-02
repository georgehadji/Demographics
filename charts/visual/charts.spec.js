// Every chart type in light, dark and print: a screenshot compared with its baseline, and
// no WCAG 2.2 A/AA violation found by axe.
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { CHARTS, page as gallery } from "./gallery.js";

// Axe reads every table cell; the default 30 s is too short for the full page.
test.setTimeout(300_000);
const pages = new Map();
const html = (mode) => pages.get(mode) ?? pages.set(mode, gallery(mode)).get(mode);

for (const mode of ["light", "dark", "print"]) {
  test.describe(mode, () => {
    test.beforeEach(async ({ page }) => {
      if (mode === "print") await page.emulateMedia({ media: "print" });
      else await page.emulateMedia({ colorScheme: mode });
      await page.setContent(html(mode));
      await page.evaluate(() => document.fonts.ready);
    });

    for (const name of Object.keys(CHARTS))
      test(`${name} looks as before`, async ({ page }) => {
        await expect(page.locator(`[data-chart="${name}"] figure`)).toHaveScreenshot(`${name}-${mode}.png`);
      });

    test("no accessibility violations", async ({ page }) => {
      await page.locator("details").evaluateAll((all) => all.forEach((d) => (d.open = true)));
      const { violations } = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(" ")}`)).toEqual([]);
    });
  });
}
