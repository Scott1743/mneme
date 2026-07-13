"""Deterministic skill-only zip builder for Mneme.

Task 10 of the 2.0 implementation plan. The single deliverable is a
zip that, when unpacked, drops ``mneme/SKILL.md`` and friends into
the user's ``~/.claude/skills/mneme/`` directory.

Design constraints:

- Sources the skill tree from ``skills/mneme/`` (the only shippable
  artefact per the v1.1+ "skill-first" delivery model).
- Prefixes every entry's ``arcname`` with ``mneme/`` so the layout
  matches Claude Code's skill convention.
- Excludes build artefacts: ``__pycache__/``, ``*.egg-info/``,
  ``*.mneme/``, ``*.pyc``, ``*.pyo``, ``.DS_Store``.
- Emits exactly one zip at ``dist/mneme-<version>.zip``, where
  ``<version>`` is read from
  ``skills/mneme/scripts/mneme/__init__.py:__version__``.
- Wipes any stale ``dist/mneme-*.zip`` before writing the new one.
- Deterministic ordering (sorted walk) and reproducible metadata so
  re-running the script produces a byte-identical zip (modulo
  current ``mtime``/``permissions``; zips use fixed-time + 0o644
  bits to match the project's other builders).
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "skills" / "mneme"
DEFAULT_OUT = ROOT / "dist"
ARC_PREFIX = "mneme"

# Stable timestamp: 1980-01-01 00:00:00 is the earliest value accepted by
# the standard ZIP format (DOS format local-file-header). Using it removes
# the mtime component from byte-level reproducibility.
_DOS_EPOCH = (1980, 1, 1, 0, 0, 0)

# Build / OS debris — never ship these inside a skill zip.
EXCLUDE_NAMES: tuple[str, ...] = (".DS_Store",)
EXCLUDE_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo")
EXCLUDE_DIR_SUFFIXES: tuple[str, ...] = (".egg-info", ".mneme")
EXCLUDE_DIR_PARTS: tuple[str, ...] = ("__pycache__",)


def _read_version(init_py: Path) -> str:
    text = init_py.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not m:
        raise SystemExit(
            f"Could not find __version__ in {init_py}; the skill package "
            f"must expose a __version__ string."
        )
    return m.group(1)


def _should_skip(path: Path, parts: Iterable[str]) -> bool:
    """Return True for entries that should not appear in the zip."""
    for part in parts:
        if part in EXCLUDE_DIR_PARTS:
            return True
        for suf in EXCLUDE_DIR_SUFFIXES:
            if part.endswith(suf):
                return True
    if path.name in EXCLUDE_NAMES:
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def _collect_files(src: Path) -> list[Path]:
    if not src.is_dir():
        raise SystemExit(f"source skill directory not found: {src}")
    files = []
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if _should_skip(p, rel.parts):
            continue
        files.append(p)
    if not files:
        raise SystemExit(f"no files to package under {src}")
    return files


def _clear_stale(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("mneme-*.zip"):
        old.unlink()


def _build(src: Path, out: Path, version: str) -> Path:
    _clear_stale(out)
    files = _collect_files(src)
    zip_path = out / f"mneme-{version}.zip"
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for p in files:
            rel = p.relative_to(src).as_posix()
            arcname = f"{ARC_PREFIX}/{rel}"
            data = p.read_bytes()
            info = zipfile.ZipInfo(arcname, date_time=_DOS_EPOCH)
            # read-only archive; preserve executable bits when present
            mode = (p.stat().st_mode & 0o777) or 0o644
            info.external_attr = (mode & 0o777) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="output directory for the zip (default: ./dist)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=SRC_DIR,
        help="skill source directory (default: ./skills/mneme)",
    )
    parser.add_argument(
        "--version",
        default=None,
        help=(
            "override the version string; by default it is read from "
            "skills/mneme/scripts/mneme/__init__.py:__version__"
        ),
    )
    args = parser.parse_args(argv)

    version = args.version or _read_version(args.src / "scripts" / "mneme" / "__init__.py")
    zip_path = _build(args.src, args.out, version)
    print(f"wrote {zip_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
