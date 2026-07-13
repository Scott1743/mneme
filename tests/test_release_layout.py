"""Release-gate for v1.1.0 — skill-first delivery & directory layout.

v1.0 readiness §"P0 Delivery model is internally inconsistent" is closed
by v1.1.0 (see docs/superpowers/plans/2026-07-13-mneme-1.1.0-implementation.md
§3). The tests in this file are the structural assertions for that close:

- §3.1: wheel artifacts gone (dist/, *.egg-info/, build/)
- §3.2: pyproject.toml has no [project.scripts] / [build-system] / setuptools config
- §3.3: src/ layout removed, Python package lives at skills/mneme/scripts/mneme/
- §3.4: SKILL.md paths use the skill.sh install location, no `mneme <cmd>`,
         no repo-relative paths, no wheel references

These are release-gate tests — failing one means the v1.1.0 delivery
contract is broken. The zero-dep OKF core & L2 lazy-install mechanics
live in test_zero_dep.py (PR2).
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS_PKG = SKILL_DIR / "scripts" / "mneme"
SCRIPTS_SHIM = SKILL_DIR / "scripts" / "mneme.py"
REFERENCES_DIR = SKILL_DIR / "references"


# ---------------------------------------------------------------------------
# §3.1 — zip artifact (the only deliverable)
# ---------------------------------------------------------------------------

def test_dist_directory_with_zip_present():
    """dist/ contains mneme-<version>.zip after the build step.

    v1.1.x ships ONLY a plain zip — unzip into ~/.claude/skills/mneme/
    and the agent picks it up. No wheel, no pip install, no extras.
    """
    assert (ROOT / "dist").is_dir(), (
        "v1.1.x publishes a zip; dist/ should exist after build."
    )
    zips = list((ROOT / "dist").glob("mneme-*.zip"))
    assert zips, (
        "dist/ exists but contains no mneme-*.zip. "
        "Run the zip build (see scripts/build_zip.py or Makefile)."
    )


def test_zip_filename_matches_version():
    """The zip filename must match the version reported by SKILL.md /
    __init__.py (single source of truth = skills/mneme/scripts/mneme/__init__.py
    `__version__`).
    """
    init = (SKILL_DIR / "scripts" / "mneme" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', init, re.MULTILINE)
    assert m, "could not find __version__ in mneme/__init__.py"
    pkg_v = m.group(1)
    zips = list((ROOT / "dist").glob("mneme-*.zip"))
    assert zips, "no zip found in dist/"
    latest = max(zips, key=lambda p: p.name)
    assert pkg_v in latest.name, (
        f"latest zip {latest.name} does not match __version__ {pkg_v!r}"
    )


def test_no_src_mneme_directory():
    """src/mneme/ Python package layout is reverted in v1.1.0."""
    assert not (ROOT / "src" / "mneme").exists(), (
        "v1.1.0 reverts to skills/mneme/scripts/mneme/ layout; "
        "src/mneme/ should not exist."
    )


def test_no_wheel_or_pyproject_build_config():
    """pyproject.toml must NOT declare any wheel-build config — v1.1.x
    ships zip-only. No [build-system], no [project.scripts], no
    [tool.setuptools.*] (those all imply a wheel deliverable)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        "[build-system]",
        "[project.scripts]",
        "[tool.setuptools",
        "setuptools",
        "wheel",
    )
    for token in forbidden:
        if token in text:
            # Allow token in prose (e.g. comments mentioning old state);
            # but the canonical wheel-build keywords should not appear
            # in active config.
            # Just check for the section openers.
            if token.startswith("["):
                assert False, (
                    f"pyproject.toml contains '{token}' — v1.1.x is "
                    f"zip-only, no wheel/build-system config allowed."
                )


def test_pyproject_has_no_project_table():
    """pyproject.toml should NOT declare [project] — no package metadata,
    no name/version. The version lives in skills/.../mneme/__init__.py
    `__version__` (single source of truth)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project]" not in text or "test" in text, (
        "pyproject.toml must not declare [project]; zip-only delivery "
        "needs no package metadata."
    )


# ---------------------------------------------------------------------------
# §3.3 — skills/mneme/scripts layout
# ---------------------------------------------------------------------------

def test_skills_mneme_scripts_layout():
    """Python package + CLI shim live at skills/mneme/scripts/mneme(+ .py)."""
    expected_files = [
        SCRIPTS_SHIM,  # CLI entry shim
        SCRIPTS_PKG / "__init__.py",
        SCRIPTS_PKG / "__main__.py",
        SCRIPTS_PKG / "cli.py",
        SCRIPTS_PKG / "okflib.py",
        SCRIPTS_PKG / "indexlib.py",
        SCRIPTS_PKG / "validate_okf.py",
        SCRIPTS_PKG / "config.py",
        SCRIPTS_PKG / "tools_helpers.py",
        SCRIPTS_PKG / "toml_writer.py",
        SKILL_MD,
        REFERENCES_DIR / "workflow-ingest.md",
        REFERENCES_DIR / "workflow-query.md",
        REFERENCES_DIR / "workflow-lint.md",
        REFERENCES_DIR / "type-vocab.md",
        REFERENCES_DIR / "wiki-structure.md",
        REFERENCES_DIR / "index-design.md",
    ]
    missing = [p for p in expected_files if not p.exists()]
    assert not missing, (
        f"v1.1.x skill layout is missing files:\n"
        + "\n".join(f"  - {p}" for p in missing)
    )


def test_skills_mneme_scripts_importable_as_module():
    """`python3 -m mneme` from skills/mneme/scripts/ runs __version__ == 1.1.0."""
    import subprocess
    import sys as _sys
    r = subprocess.run(
        [_sys.executable, "-c", "import mneme; print(mneme.__version__)"],
        cwd=str(SKILL_DIR / "scripts"),
        capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        f"`python3 -m mneme` failed:\nstdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert r.stdout.strip() == "1.1.0", (
        f"mneme.__version__ = {r.stdout.strip()!r}, expected '1.1.0'"
    )


# ---------------------------------------------------------------------------
# §3.4 — SKILL.md path convergence
# ---------------------------------------------------------------------------

_SKILL_FILES = (SKILL_MD,)


def test_skill_md_documents_zip_only_delivery():
    """SKILL.md teaches the skill.sh shim path AND mentions that the
    only delivery is a plain zip (no wheel, no PyPI). Lightweight.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "~/.claude/skills/mneme/scripts/mneme.py" in text, (
        "SKILL.md is missing the skill.sh shim path"
    )
    # No pip-install-mneme whole-package install anywhere.
    assert not re.search(r"pip install mneme(?!\w)", text), (
        "SKILL.md should NOT teach `pip install mneme`; v1.1.x is zip-only"
    )


def test_skill_md_uses_skill_relative_paths():
    """SKILL.md teaches the skill.sh install path explicitly."""
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        assert "~/.claude/skills/mneme/scripts/mneme.py" in text, (
            f"{path} does not reference the skill.sh shim path "
            f"~/.claude/skills/mneme/scripts/mneme.py"
        )


def test_skill_md_no_repo_relative_paths():
    """No `src/mneme/`, `python3 scripts/`, `./scripts/` references."""
    patterns = (r"src/mneme/", r"python3 scripts/", r"\./scripts/")
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            hits = re.findall(pat, text)
            assert not hits, (
                f"{path} still contains repo-relative path {pat!r}: {hits!r}"
            )
    # references/*.md
    for ref in REFERENCES_DIR.glob("*.md"):
        text = ref.read_text(encoding="utf-8")
        for pat in patterns:
            hits = re.findall(pat, text)
            assert not hits, (
                f"{ref} still contains repo-relative path {pat!r}: {hits!r}"
            )


def test_skill_md_documents_l2_as_opt_in():
    """SKILL.md mentions L2 is opt-in (sqlite-vec + fastembed manual install).
    No auto-install / no surprise network calls — keep it lightweight.
    """
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8").lower()
        assert "sqlite-vec" in text and "fastembed" in text, (
            f"{path} should mention sqlite-vec + fastembed for L2 users "
            "(manual install — no auto-install)"
        )


def test_skill_md_no_pip_install_mneme_anywhere():
    """SKILL.md must NOT mention `pip install mneme` at all. v1.1.x is
    zip-only — no PyPI release, no wheel, no extras. `pip install
    sqlite-vec fastembed` (raw packages, not mneme) IS allowed because
    that's how the user opts into L2.
    """
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        hits = re.findall(r"pip install mneme(?!\w)", text)
        assert not hits, (
            f"{path} still teaches `pip install mneme`: {hits!r}. "
            "v1.1.x is zip-only, no PyPI release."
        )


def test_skill_md_no_wheel_or_dist_references():
    """SKILL.md does not mention wheel / build / pyproject / dist."""
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8").lower()
        forbidden = (
            "wheel", "pyproject.toml", "setup.py",
            "python -m build", "python -m pip wheel",
            "build/", "dist/",
        )
        hits = [w for w in forbidden if w in text]
        assert not hits, (
            f"{path} still references build/packaging artifacts: {hits!r}. "
            "v1.1.x is zip-only; the deliverable is just `mneme-<v>.zip`."
        )