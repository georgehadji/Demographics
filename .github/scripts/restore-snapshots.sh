#!/usr/bin/env bash
# Restores into pipeline/store the snapshots the build reads, from the `snapshots`
# release: every manifest part, then each object the build needs. Run from pipeline/.
# Extra arguments go to grpop-build (e.g. --pin snapshots.txt).
set -euo pipefail
mkdir -p store/objects parts
gh release download snapshots -p 'manifest-*.jsonl' -D parts
cat $(ls parts/manifest-*.jsonl | sort) > store/manifest.jsonl
shas=$(uv run grpop-build --store store --list-snapshots "$@")
for sha in $shas; do
  gh release download snapshots -p "$sha" -D store/objects
done
