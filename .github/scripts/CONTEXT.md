# .github/scripts/

Shell steps shared by several workflows, so each is written once.

| File | What it does |
|---|---|
| `restore-snapshots.sh` | Restores the snapshots the build reads from the `snapshots` release into `pipeline/store`; extra arguments go to `grpop-build --list-snapshots` (e.g. `--pin`). Used by `Build` and `Publish` |
