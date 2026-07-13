"""Release-gate — version integrity.

``__version__`` in ``skills/mneme/scripts/mneme/__init__.py`` is the single
source of truth. ``pyproject.toml`` is pytest-only and MUST NOT carry any
packaging configuration: no ``[project]``, no ``[build-system]``, no
``[project.scripts]``, no ``[tool.setuptools]``, no ``setup(...)``.
"""
import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
INIT_PY = ROOT / "skills" / "mneme" / "scripts" / "mneme" / "__init__.py"
SKILL_FILES = (
    ROOT / "skills" / "mneme" / "SKILL.md",
)


def _init_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, f"could not find `__version__ = ...` in {INIT_PY}"
    return match.group(1)


def test_all_skill_manifests_have_release_version():
    """SKILL.md frontmatter `version` matches the package __version__."""
    expected = _init_version()
    for path in SKILL_FILES:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^version:\s*([^\s]+)\s*$", text, re.MULTILINE)
        assert match, f"{path} must declare a version in YAML frontmatter"
        assert match.group(1).strip('"\'') == expected, (
            f"version drift: {path}={match.group(1)!r}, expected {expected!r}"
        )


def test_version_is_release_gate():
    """1.0.0 is the release-contract gate. Below 1.0.0 means partial
    behavior is allowed; at or above 1.0.0 the readiness-assessment
    release gate MUST be closed.
    """
    version = _init_version()
    major = int(version.split(".")[0])
    assert major >= 1, (
        f"version {version!r} is below 1.0.0 — release gate not yet closed."
    )


def test_pyproject_is_pure_pytest_config():
    """pyproject.toml is pytest-only — no packaging metadata, no build
    system, no setuptools configuration, no wheel entry point."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    forbidden_sections = (
        "[project]",
        "[build-system]",
        "[project.scripts]",
        "[tool.setuptools",
    )
    hits = [section for section in forbidden_sections if section in text]
    assert not hits, (
        "pyproject.toml must remain pytest-only: " + ", ".join(hits)
    )
    assert "setup(" not in text, "pyproject.toml must not call setup()"
