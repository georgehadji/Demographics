// Called by the shortcodes in kohortes.lua; prints HTML, or exits non-zero with the reason,
// which stops the render. The data product directory is $KOHORTES_DATA.
//   node src/cli.js fact <name> <geo> <period> [sex] [age]
//   node src/cli.js chart <spec.json, relative to site/>
//   node src/cli.js brand   (writes _brand/light.yml and dark.yml from design/tokens.json)
//   node src/cli.js pages   (writes the pages made from the data product, src/pages.js)
//   node src/cli.js links   (fails on a broken local link in _site)
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { brand } from "../../design/src/build.js";
import { brokenLinks } from "./links.js";
import { writePages } from "./pages.js";
import { chart, fact } from "./product.js";

const SITE = new URL("../", import.meta.url);
const [command, ...args] = process.argv.slice(2);
const dir = process.env.KOHORTES_DATA;
try {
  if (command === "fact") process.stdout.write(fact(dir, ...args));
  else if (command === "chart") process.stdout.write(chart(dir, JSON.parse(readFileSync(new URL(args[0], SITE), "utf8"))));
  else if (command === "brand") {
    mkdirSync(new URL("_brand/", SITE), { recursive: true });
    writeFileSync(new URL("_brand/light.yml", SITE), brand("light"));
    writeFileSync(new URL("_brand/dark.yml", SITE), brand("dark"));
  } else if (command === "pages") writePages(dir);
  else if (command === "links") {
    const broken = brokenLinks(fileURLToPath(new URL("_site", SITE)));
    if (broken.length) throw new Error(`broken links:\n${broken.join("\n")}`);
  } else throw new Error(`unknown command ${command}`);
} catch (e) {
  console.error(`kohortes: ${e.message}`);
  process.exit(1);
}
