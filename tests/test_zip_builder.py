"""Tests for the deterministic skill-only zip builder.

Task 10 of the 2.0 implementation plan. The builder must:

- Source its tree from ``skills/mneme/``
- Prefix every arcname with ``mneme/`` so the unpacked layout
  matches the layout Claude Code expects under
  ``~/.claude/skills/mneme/``
- Exclude Python bytecode / build / OS debris
- Emit exactly one zip into ``dist/mneme-<version>.zip`` where
  ``<version>`` is read from
  ``skills/mneme/scripts/mneme/__init__.py:__version__``
- Clear stale ``dist/mneme-*.zip`` before writing
- Produce a zip whose contents are a byte-level superset of
  ``skills/mneme/`` (filtered for build artefacts)
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "skills" / "mneme"
OUT = ROOT / "dist"
BUILDER = ROOT / "scripts" / "build_zip.py"


def _run_builder(*, out_dir: Path | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(BUILDER)]
    if out_dir is not None:
        argv += ["--out", str(out_dir)]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT))


def _read_version() -> str:
    init_text = (PKG / "scripts" / "mneme" / "__init__.py").read_text()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_text)
    assert m, f"__version__ not found in __init__.py:\n{init_text}"
    return m.group(1)


def test_build_zip_creates_exactly_one_zip():
    cp = _run_builder(out_dir=OUT)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    zips = sorted(OUT.glob("mneme-*.zip"))
    assert len(zips) == 1, f"expected exactly one zip, got {zips}"


def test_zip_contents_match_skills_tree():
    version = _read_version()
    expected_zip = OUT / f"mneme-{version}.zip"
    # Idempotent: re-run to confirm clean rebuild
    cp = _run_builder(out_dir=OUT)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert expected_zip.is_file(), f"missing expected {expected_zip}"

    with zipfile.ZipFile(expected_zip) as zf:
        names = {n.split("/", 1)[1] for n in zf.namelist() if "/" in n}

    src_files: set[str] = set()
    for p in PKG.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.parts)
        if "__pycache__" in parts:
            continue
        if any(part.endswith(".egg-info") for part in parts):
            continue
        if any(part.endswith(".mneme") for part in parts):
            continue
        suffix = p.suffix
        if suffix in {".pyc", ".pyo"}:
            continue
        if p.name == ".DS_Store":
            continue
        if p.name == "skill_cn.md":
            continue
        src_files.add(str(p.relative_to(PKG)))

    missing = src_files - names
    assert not missing, f"zip is missing files present in skills/mneme/: {sorted(missing)}"
    # And every name inside the zip must have the mneme/ prefix
    with zipfile.ZipFile(expected_zip) as zf:
        for n in zf.namelist():
            assert n.startswith("mneme/"), f"arcname missing mneme/ prefix: {n!r}"


def test_zip_contains_web_console_modules():
    """v4.2 ships the `mneme serve` console inside the skill zip."""
    cp = _run_builder(out_dir=OUT)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    version = _read_version()
    with zipfile.ZipFile(OUT / f"mneme-{version}.zip") as zf:
        names = set(zf.namelist())
    assert "mneme/scripts/mneme/webserver.py" in names
    assert "mneme/scripts/mneme/webui.py" in names
    assert "mneme/scripts/mneme/vendor/g6-5.1.1.min.js" in names
    assert "mneme/scripts/mneme/vendor/antv-g6-LICENSE.txt" in names
    assert "mneme/scripts/mneme/vendor/THIRD_PARTY_NOTICES.md" in names


def test_excludes_pycache_and_egg_info():
    cp = _run_builder(out_dir=OUT)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    version = _read_version()
    zip_path = OUT / f"mneme-{version}.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    for n in names:
        assert "__pycache__" not in n, f"zip contains __pycache__: {n}"
        assert ".egg-info" not in n, f"zip contains .egg-info: {n}"
        assert ".pyc" not in n, f"zip contains .pyc: {n}"
        assert ".pyo" not in n, f"zip contains .pyo: {n}"
        assert ".DS_Store" not in n, f"zip contains .DS_Store: {n}"
        assert not n.endswith("/skill_cn.md"), (
            f"zip contains local-only Chinese reference: {n}"
        )


def test_clears_stale_zips():
    # Plant a stale zip that the new build should overwrite
    stale = OUT / "mneme-9.9.9.zip"
    OUT.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"stale")
    try:
        cp = _run_builder(out_dir=OUT)
        assert cp.returncode == 0, cp.stdout + cp.stderr
        assert not stale.exists(), "stale zip not removed before rebuild"
        zips = sorted(OUT.glob("mneme-*.zip"))
        assert len(zips) == 1, f"expected one zip after stale cleanup, got {zips}"
    finally:
        if stale.exists():
            stale.unlink()


def test_default_out_is_dist():
    # Run with no --out: must default to ./dist
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("mneme-*.zip"):
        old.unlink()
    cp = _run_builder()
    assert cp.returncode == 0, cp.stdout + cp.stderr
    zips = list(OUT.glob("mneme-*.zip"))
    assert len(zips) == 1, f"default --out did not land in dist: {zips}"
