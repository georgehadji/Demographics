// Visual regression and accessibility tests of the charts (PROPOSAL §7A). Baselines are
// Linux screenshots made in CI (the Playwright container with fonts-noto-core); a local
// run on another platform writes its own, which git ignores. PW_CHANNEL=chrome uses an
// installed Chrome instead of Playwright's browser.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "visual",
  snapshotPathTemplate: "{testDir}/snapshots/{arg}-{platform}{ext}",
  reporter: [["list"], ["html", { open: "never" }]],
  use: { browserName: "chromium", channel: process.env.PW_CHANNEL, viewport: { width: 1000, height: 800 } },
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0.002 } },
});
