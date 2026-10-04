// Axe on every kind of page of the rendered site (_site), in light and dark mode.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "test",
  testMatch: "*.spec.js",
  use: { channel: process.env.PW_CHANNEL },
});
