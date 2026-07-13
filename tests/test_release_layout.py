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
SKILL_CN_MD = SKILL_DIR / "SKILL cn.md"
SCRIPTS_PKG = SKILL_DIR / "scripts" / "mneme"
SCRIPTS_SHIM = SKILL_DIR / "scripts" / "mneme.py"
REFERENCES_DIR = SKILL_DIR / "references"


# ---------------------------------------------------------------------------
# §3.1 — wheel artifacts gone
# ---------------------------------------------------------------------------

def test_no_dist_directory_after_1_1():
    """dist/ must not exist on disk in v1.1.0+. wheel builds are gone."""
    assert not (ROOT / "dist").exists(), (
        "v1.1.0 stopped shipping wheels; dist/ should not exist. "
        "Run `rm -rf dist/` and update .gitignore if needed."
    )


def test_no_egg_info_directory():
    """*.egg-info/ must not exist. setuptools no longer runs."""
    for path in ROOT.rglob("*.egg-info"):
        if path.is_dir():
            pytest.fail(f"v1.1.0 stopped setuptools builds; {path} still exists")


def test_no_build_directory():
    """build/ (setuptools build tree) must not exist."""
    assert not (ROOT / "build").exists(), (
        "v1.1.0 stopped setuptools builds; build/ should not exist."
    )


def test_no_src_mneme_directory():
    """src/mneme/ Python package layout is reverted in v1.1.0."""
    assert not (ROOT / "src" / "mneme").exists(), (
        "v1.1.0 reverts to skills/mneme/scripts/mneme/ layout; "
        "src/mneme/ should not exist."
    )


# ---------------------------------------------------------------------------
# §3.2 — pyproject.toml cleanup
# ---------------------------------------------------------------------------

def _pyproject_text() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def test_pyproject_no_project_scripts():
    """[project.scripts] is gone — no console-script entry point."""
    text = _pyproject_text()
    assert "[project.scripts]" not in text, (
        "v1.1.0 dropped the `mneme` console command; "
        "[project.scripts] should be removed from pyproject.toml."
    )
    assert "mneme = " not in text or "mneme = " not in re.findall(
        r"^[a-zA-Z_]\w*\s*=", text, re.MULTILINE
    ), "no `mneme = ...` console-script mapping expected"


def test_pyproject_no_build_system():
    """[build-system] is gone — no wheel build."""
    text = _pyproject_text()
    assert "[build-system]" not in text, (
        "v1.1.0 stopped building wheels; [build-system] should be removed."
    )


def test_pyproject_no_setuptools_config():
    """All [tool.setuptools.*] config is gone."""
    text = _pyproject_text()
    assert "[tool.setuptools" not in text, (
        "v1.1.0 stopped using setuptools; "
        "[tool.setuptools.packages.find] and [tool.setuptools.package-data] "
        "should be removed from pyproject.toml."
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
        # toml_writer.py and lazy_index.py land in PR2; tested there.
        SKILL_MD,
        SKILL_CN_MD,
        REFERENCES_DIR / "workflow-ingest.md",
        REFERENCES_DIR / "workflow-query.md",
        REFERENCES_DIR / "workflow-lint.md",
        REFERENCES_DIR / "type-vocab.md",
        REFERENCES_DIR / "wiki-structure.md",
        REFERENCES_DIR / "index-design.md",
    ]
    missing = [p for p in expected_files if not p.exists()]
    assert not missing, (
        f"v1.1.0 skill layout is missing files:\n"
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

_SKILL_FILES = (SKILL_MD, SKILL_CN_MD)


def test_skill_md_no_mneme_console_command():
    """SKILL.md does NOT teach `mneme init` etc. as a console command.

    Replaced with the skill.sh path:
    `python3 ~/.claude/skills/mneme/scripts/mneme.py <subcmd>`
    """
    for path in _SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        # Look for "mneme <subcmd>" patterns (e.g. "mneme init", "mneme reindex").
        # Exclude legitimate mentions inside the skill.sh path itself.
        offending = re.findall(r"\b(mneme\s+(?:init|reindex|search|lint|install))\b", text)
        assert not offending, (
            f"{path} still references the dropped console command: "
            f"{set(offending)!r}. Replace with the skill.sh shim path."
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