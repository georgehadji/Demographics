// No WCAG 2.2 A/AA violation found by axe on one page of each kind, in light and dark mode
// (Build workflow, after the render).
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const SITE = new URL("../_site/", import.meta.url);
const PAGES = ["index.html", "indicators/index.html", "indicators/total_fertility_rate.html", "definitions.html", "sources.html", "ai.html", "errata.html"];

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
