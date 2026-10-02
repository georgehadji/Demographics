# AGENTS.md

Instructions for coding agents working in this repository.

1. **Start with [`CONTEXT.md`](CONTEXT.md).** It says what the project does, maps every folder, and links each folder's own `CONTEXT.md`, which describes every file in it. Use these maps to find files before searching.
2. **Follow [`CLAUDE.md`](CLAUDE.md).** It holds the project's rules (provenance, single source of truth, design system, how to work in `pipeline/` and `design/`). They apply to every agent, not only Claude Code. This file does not repeat them.
3. **Keep the maps true.** When you add, remove, rename or repurpose a file, update the `CONTEXT.md` of its folder in the same change (and the root map for a new folder). `pipeline/tests/test_context.py` fails otherwise.
