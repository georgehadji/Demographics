"""The CONTEXT.md maps match the tracked files (ADR 0006: a test enforces what can be checked).

Every folder that holds tracked files has a CONTEXT.md listing each file and subfolder
in a table row that starts with its name in backticks. The root CONTEXT.md lists the
root files and links every folder's map. Files staged but not committed count as
tracked, so a new file fails here before it is pushed.
"""

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
ROW = re.compile(r"^\| `([^`]+)` \|", re.MULTILINE)


def tracked() -> list[PurePosixPath]:
    out = subprocess.run(
        ["git", "ls-files", "--cached"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [PurePosixPath(line) for line in out.splitlines() if line]


def children() -> dict[PurePosixPath, set[str]]:
    """Folder -> names of its tracked files and of its subfolders that hold tracked files."""
    out: dict[PurePosixPath, set[str]] = {}
    for path in tracked():
        if path.name != "CONTEXT.md":
            out.setdefault(path.parent, set()).add(path.name)
        for parent in path.parents:
            if parent != PurePosixPath("."):
                out.setdefault(parent.parent, set()).add(parent.name)
    return out


def listed(folder: PurePosixPath) -> set[str]:
    return set(ROW.findall((ROOT / folder / "CONTEXT.md").read_text(encoding="utf-8")))


def test_every_folder_map_lists_exactly_its_files():
    for folder, names in children().items():
        if folder == PurePosixPath(".") or not any((ROOT / folder / n).is_file() for n in names):
            continue  # the root is checked below; folders holding only folders need no map
        assert (ROOT / folder / "CONTEXT.md").is_file(), f"{folder}/CONTEXT.md is missing"
        rows = listed(folder)
        assert names <= rows, f"{folder}/CONTEXT.md does not list {sorted(names - rows)}"
        assert rows <= names, f"{folder}/CONTEXT.md lists missing files {sorted(rows - names)}"


def test_root_map_lists_root_files_and_links_every_folder_map():
    tree = children()
    root_files = {n for n in tree[PurePosixPath(".")] if (ROOT / n).is_file()}
    text = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    rows = listed(PurePosixPath("."))
    assert root_files <= rows, f"CONTEXT.md does not list {sorted(root_files - rows)}"
    maps = {str(f) for f in tree if f != PurePosixPath(".") and (ROOT / f / "CONTEXT.md").is_file()}
    assert all(f"({m}/CONTEXT.md)" in text for m in maps), "a folder map is not linked"
    stale = rows - root_files - maps
    assert not stale, f"CONTEXT.md lists missing paths {sorted(stale)}"
