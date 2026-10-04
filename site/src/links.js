// Every local link and source in the rendered site (_site) points to a file that exists.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

const walk = (dir) =>
  readdirSync(dir).flatMap((f) => (statSync(join(dir, f)).isDirectory() ? walk(join(dir, f)) : [join(dir, f)]));

/** "page.html: target" for every broken local href or src under root. */
export function brokenLinks(root) {
  const broken = [];
  for (const file of walk(root).filter((f) => f.endsWith(".html"))) {
    for (const [, url] of readFileSync(file, "utf8").matchAll(/(?:href|src)="([^"]*)"/g)) {
      if (!url || /^(?:[a-z]+:|#|\/\/)/i.test(url)) continue; // external, data:, mailto:, in-page
      const path = decodeURIComponent(url.split(/[?#]/)[0]);
      // The site is served under /Demographics/ on GitHub Pages: a root-absolute link breaks.
      if (path.startsWith("/")) {
        broken.push(`${file.slice(root.length + 1)}: ${url} (absolute)`);
        continue;
      }
      const target = resolve(dirname(file), path);
      const ok = existsSync(target) && (!statSync(target).isDirectory() || existsSync(join(target, "index.html")));
      if (!ok) broken.push(`${file.slice(root.length + 1)}: ${url}`);
    }
  }
  return broken;
}
