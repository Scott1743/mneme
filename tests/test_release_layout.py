"""Release-gate for skill-first delivery and directory layout.

The Python package lives inside the delivered skill. ``__version__`` in
``skills/mneme/scripts/mneme/__init__.py`` is the release-version source of
truth; release archives, when present, must derive their name from it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "mneme"
SKILL_MD = SKILL_DIR / "SKILL.md"
SCRIPTS_PKG = SKILL_DIR / "scripts" / "mneme"
SCRIPTS_SHIM = SKILL_DIR / "scripts" / "mneme.py"
REFERENCES_DIR = SKILL_DIR / "references"


def _version() -> str:
    text = (SCRIPTS_PKG / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "could not find __version__ in mneme/__init__.py"
    return match.group(1)


def test_release_archive_name_matches_version_when_present():
    """A built checkout contains at most one correctly named skill archive.

    Building the archive is a separate release step, so a source checkout may
    have no ``dist/`` directory at all.
    """
    archives = list((ROOT / "dist").glob("mneme-*.zip"))
    assert len(archives) <= 1, f"expected at most one skill archive: {archives}"
    if archives:
        assert archives[0].name == f"mneme-{_version()}.zip"


def test_no_src_mneme_directory():
    assert not (ROOT / "src" / "mneme").exists(), (
        "the Python package must live under skills/mneme/scripts/mneme/"
    )


def test_pyproject_has_no_packaging_config():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden = (
        "[build-system]",
        "[project]",
        "[project.scripts]",
        "[tool.setuptools",
    )
    hits = [token for token in forbidden if token in text]
    assert not hits, f"pyproject.toml must remain pytest-only: {hits}"


def test_skills_mneme_scripts_layout():
    expected_files = [
        SCRIPTS_SHIM,
        SCRIPTS_PKG / "__init__.py",
        SCRIPTS_PKG / "__main__.py",
        SCRIPTS_PKG / "cli.py",
        SCRIPTS_PKG / "okflib.py",
        SCRIPTS_PKG / "indexlib.py",
        SCRIPTS_PKG / "graphlib.py",
        SCRIPTS_PKG / "validate_okf.py",
        SCRIPTS_PKG / "config.py",
        SCRIPTS_PKG / "tools_helpers.py",
        SCRIPTS_PKG / "toml_writer.py",
        SCRIPTS_PKG / "convert.py",
        SKILL_MD,
        REFERENCES_DIR / "workflow-dream.md",
        REFERENCES_DIR / "workflow-search.md",
        REFERENCES_DIR / "workflow-lint.md",
        REFERENCES_DIR / "type-vocab.md",
        REFERENCES_DIR / "wiki-structure.md",
        REFERENCES_DIR / "index-design.md",
    ]
    missing = [path for path in expected_files if not path.exists()]
    assert not missing, "skill layout is missing files:\n" + "\n".join(
        f"  - {path}" for path in missing
    )
    assert not (REFERENCES_DIR / "workflow-ingest.md").exists()
    assert not (REFERENCES_DIR / "workflow-query.md").exists()


def test_skills_mneme_scripts_importable_as_module():
    result = subprocess.run(
        [sys.executable, "-c", "import mneme; print(mneme.__version__)"],
        cwd=str(SKILL_DIR / "scripts"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"`python3 -m mneme` failed:\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert result.stdout.strip() == _version()


def test_skill_md_uses_skill_relative_paths():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "~/.claude/skills/mneme/scripts/mneme.py" in text


def test_skill_docs_have_no_repo_relative_paths():
    patterns = (r"src/mneme/", r"python3 scripts/", r"\./scripts/")
    for path in (SKILL_MD, *REFERENCES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            hits = re.findall(pattern, text)
            assert not hits, f"{path} contains repo-relative path {pattern!r}: {hits!r}"


def test_skill_md_no_package_install_command():
    text = SKILL_MD.read_text(encoding="utf-8")
    hits = re.findall(r"pip install mneme(?!\w)", text)
    assert not hits, f"SKILL.md teaches an unsupported package install: {hits!r}"


def test_skill_md_no_packaging_artifact_references():
    text = SKILL_MD.read_text(encoding="utf-8").lower()
    forbidden = (
        "pyproject.toml",
        "setup.py",
        "python -m build",
        "build/",
        "dist/",
    )
    hits = [token for token in forbidden if token in text]
    assert not hits, f"SKILL.md references repository packaging artifacts: {hits!r}"
