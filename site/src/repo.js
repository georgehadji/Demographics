// Links into the code repository, whose address lives in CITATION.cff (ADR 0006).
import { readFileSync } from "node:fs";
import yaml from "js-yaml";

const REPO = yaml.load(readFileSync(new URL("../../CITATION.cff", import.meta.url), "utf8"))["repository-code"];
if (!REPO) throw new Error("CITATION.cff has no repository-code");

/** A file of the repository on its main branch, e.g. blob("pipeline/src/grpop/definitions.yaml"). */
export const blob = (path) => `${REPO}/blob/main/${path}`;
export const DEFINITIONS = blob("pipeline/src/grpop/definitions.yaml");
export const REGISTRY = blob("pipeline/src/grpop/sources/registry.yaml");
