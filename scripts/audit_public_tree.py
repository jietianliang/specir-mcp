#!/usr/bin/env python3
"""Fail when release files look like private inputs or generated knowledge."""
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".pdf", ".safetensors", ".pptx",
    ".zip", ".tar", ".gz",
}
FORBIDDEN_PARTS = {
    ".claude", ".cursor", ".opencode", "specs", "parsed", "data",
    "__pycache__", ".pytest_cache",
}
FORBIDDEN_TEXT = (
    "/home/", "/root/", "maxio-tech.com", "NVM-Express-",
    "Management Component Transport Protocol", "MIPI I3C",
)
MAX_FILE_SIZE = 1_000_000


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).split(b"\0")
    return [ROOT / item.decode() for item in output if item]


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden extension: {relative}")
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            problems.append(f"forbidden path: {relative}")
        if path.stat().st_size > MAX_FILE_SIZE:
            problems.append(f"file too large: {relative}")
        if (
            relative != Path("scripts/audit_public_tree.py")
            and path.suffix.lower() in {".py", ".md", ".toml", ".json", ".yml", ".yaml"}
        ):
            text = path.read_text(encoding="utf-8", errors="replace")
            for forbidden in FORBIDDEN_TEXT:
                if forbidden in text:
                    problems.append(f"forbidden text {forbidden!r}: {relative}")
    if problems:
        print("\n".join(sorted(set(problems))))
        return 1
    print(f"public tree audit passed ({len(tracked_files())} tracked files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
