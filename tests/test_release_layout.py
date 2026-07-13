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
# §3.1 — wheel artifacts present (dist/ is back for v1.1.x hybrid delivery)
# ---------------------------------------------------------------------------

def test_dist_directory_with_wheel_present():
    """dist/ contains the built wheel after `python -m build --wheel`.

    v1.1.x ships BOTH skill.sh (primary) AND a pip-installable wheel
    (for users who prefer the standard Python install path). The wheel
    is built into dist/ and CI keeps it fresh.
    """
    assert (ROOT / "dist").is_dir(), (
        "v1.1.x publishes a wheel; dist/ should exist after build."
    )
    wheels = list((ROOT / "dist").glob("mneme-*-py3-none-any.whl"))
    assert wheels, (
        "dist/ exists but contains no mneme-*-py3-none-any.whl. "
        "Run `python -m build --wheel`."
    )


def test_wheel_filename_matches_pyproject_version():
    """The wheel filename must match pyproject.toml's `version = "..."`.

    Filename and version drift is the #1 release-prep bug in this repo
    (1.0 readiness §"Install-to-query"). This test catches it.
    """
    pyproject_v = _pyproject_version()
    wheels = list((ROOT / "dist").glob("mneme-*-py3-none-any.whl"))
    assert wheels, "no wheel found in dist/"
    latest = max(wheels, key=lambda p: p.name)
    assert pyproject_v in latest.name, (
        f"latest wheel {latest.name} does not match pyproject.toml "
        f"version {pyproject_v!r}"
    )


def test_no_src_mneme_directory():
    """src/mneme/ Python package layout is reverted in v1.1.0."""
    assert not (ROOT / "src" / "mneme").exists(), (
        "v1.1.0 reverts to skills/mneme/scripts/mneme/ layout; "
        "src/mneme/ should not exist."
    )


# ---------------------------------------------------------------------------
# §3.2 — pyproject.toml hybrid setup (wheel + zero-dep core)
# ---------------------------------------------------------------------------

def _pyproject_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def _pyproject_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', _pyproject_text(), re.MULTILINE)
    assert m, "could not find `version = ...` in pyproject.toml"
    return m.group(1)


def test_pyproject_has_project_scripts():
    """[project.scripts] exposes the `mneme` console command for pip installs."""
    text = _pyproject_text()
    assert "[project.scripts]" in text, (
        "v1.1.x hybrid delivery needs the `mneme` console command; "
        "[project.scripts] should declare `mneme = mneme.cli:main`."
    )
    assert re.search(
        r'^mneme\s*=\s*"mneme\.cli:main"', text, re.MULTILINE
    ), "expected `mneme = \"mneme.cli:main\"` console-script mapping"


def test_pyproject_has_build_system():
    """[build-system] is present so `python -m build --wheel` works."""
    text = _pyproject_text()
    assert "[build-system]" in text, (
        "v1.1.x publishes a wheel; [build-system] is required."
    )
    assert "setuptools" in text and "wheel" in text, (
        "[build-system] requires should include setuptools and wheel"
    )


def test_pyproject_setuptools_config_points_at_skills_dir():
    """[tool.setuptools.packages.find] points at the skill-first layout."""
    text = _pyproject_text()
    assert "[tool.setuptools" in text, (
        "v1.1.x needs [tool.setuptools.packages.find] to discover the package "
        "at skills/mneme/scripts/mneme/."
    )
    # Confirm `where` points at the skill-first directory.
    m = re.search(
        r'\[tool\.setuptools\.packages\.find\]\s*\nwhere\s*=\s*\[([^\]]+)\]',
        text, re.MULTILINE,
    )
    assert m, "could not find `where = [...]` in [tool.setuptools.packages.find]"
    wheres = m.group(1)
    assert "skills/mneme/scripts" in wheres, (
        f"[tool.setuptools.packages.find] should point at "
        f"skills/mneme/scripts; got {wheres!r}"
    )


def test_pyproject_dependencies_empty():
    """[project].dependencies is empty (zero hard deps for OKF core)."""
    text = _pyproject_text()
    m = re.search(
        r'^dependencies\s*=\s*\[(.*?)\]',
        text, re.MULTILINE | re.DOTALL,
    )
    assert m, "could not find `dependencies = [...]` in pyproject.toml"
    body = m.group(1).strip()
    assert body == "", (
        f"[project].dependencies must be empty for zero-dep OKF core; "
        f"got {body!r}"
    )


def test_pyproject_optional_extras_index_and_validate_present():
    """[project.optional-dependencies] keeps `index` (L2 lazy) + `validate`."""
    text = _pyproject_text()
    assert "[project.optional-dependencies]" in text, (
        "optional-dependencies block missing; v1.1.0 keeps `index` + `validate` extras"
    )
    # Each extras key is matched on its own line.
    assert re.search(r"^index\s*=\s*\[", text, re.MULTILINE), (
        "`index` extra (sqlite-vec + fastembed) missing — L2 lazy install target"
    )
    assert re.search(r'^validate\s*=\s*\[', text, re.MULTILINE), (
        "`validate` extra (PyYAML) missing — strict YAML verification opt-in"
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
        SCRIPTS_PKG / "lazy_index.py",
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


def test_skill_md_documents_both_delivery_paths():
    """SKILL.md mentions BOTH the `mneme` console command (pip install)
    AND the skill.sh path (skill-first delivery). The two paths are
    interchangeable for the user; SKILL.md should make that explicit.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "~/.claude/skills/mneme/scripts/mneme.py" in text, (
        "SKILL.md is missing the skill.sh shim path; the skill-first "
        "delivery needs it for users who didn't pip install."
    )
    # The console command is mentioned in the L2 lazy-install note.
    assert "mneme[index]" in text, (
        "SKILL.md should mention `pip install 'mneme[index]'` as the "
        "offline fallback for L2 lazy install."
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


def test_skill_md_documents_l2_lazy_install():
    """SKILL.md mentions L2 lazy install (so first-time users aren't surprised)."""
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        assert "ensure_index_deps" in text or "lazy" in text.lower() or "lazy-installed" in text.lower(), (
            f"{path} should document L2 lazy install (ensure_index_deps / "
            "lazy install behaviour) so first-time users aren't surprised."
        )


def test_skill_md_no_pip_install_mneme_whole_package():
    """SKILL.md does NOT teach `pip install mneme` (whole-package install).

    `pip install mneme[index]` is ALLOWED — it's the offline fallback
    for the L2 lazy install, not a full install instruction.
    """
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        # Match `pip install mneme` NOT followed by `[`.
        hits = re.findall(r"pip install mneme(?!\[\w)", text)
        assert not hits, (
            f"{path} still teaches `pip install mneme` (whole-package install): "
            f"{hits!r}. v1.1.0 ships via skill.sh, not PyPI."
        )


def test_skill_md_no_wheel_or_dist_references():
    """SKILL.md does not mention wheel / build / pyproject in active scenarios."""
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8").lower()
        forbidden = (
            "wheel", "pyproject.toml", "setup.py",
            "python -m build", "python -m pip wheel",
        )
        hits = [w for w in forbidden if w in text]
        assert not hits, (
            f"{path} still references build/packaging: {hits!r}. "
            "v1.1.0 is skill-first; build references belong in CLAUDE.md / docs/."
        )