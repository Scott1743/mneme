"""Release-gate §3.4 — version integrity.

The v0.3.0 freeze introduced version pinning but the test only listed
acceptable markers as module constants — it never asserted anything.
Two real bugs slipped through:

1. ``src/mneme/__init__.py`` stayed at ``__version__ = "0.3.0"`` while
   ``pyproject.toml`` rolled forward through 0.4.0 → 0.5.0 → 0.6.0 →
   0.6.1. ``import mneme; mneme.__version__`` lied.
2. The release-gate had no test asserting that 1.0.0 actually means
   1.0.0 — a stale ``0.x`` marker would silently pass.

This module now closes both gaps. It is the single source of truth for
"the version we ship is the version we say we ship".
"""
import re
from pathlib import Path
import pytest
pytestmark = pytest.mark.release

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "mneme" / "__init__.py"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, f"could not find `version = ...` in {PYPROJECT}"
    return m.group(1)


def _init_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, f"could not find `__version__ = ...` in {INIT_PY}"
    return m.group(1)


def test_pyproject_and_init_version_agree():
    """The two version sources MUST agree. Without this test, an
    editable install reports a different ``__version__`` than the
    wheel metadata — exactly the drift that left 0.6.1 shipping
    while ``mneme.__version__`` still said "0.3.0".
    """
    py = _pyproject_version()
    init = _init_version()
    assert py == init, (
        f"version drift: pyproject.toml={py!r} but "
        f"src/mneme/__init__.py={init!r}. Update both to the same value."
    )


def test_version_is_release_gate():
    """1.0.0 is the release-contract gate. Below 1.0.0 means partial
    behavior is allowed; at or above 1.0.0 the readiness-assessment
    release gate MUST be closed (all P0/P1 resolved, install-to-query
    works from the release artifact, dream excluded, retrieval meets
    the labeled real-corpus gates, resource budgets documented, CI
    green).

    This test does NOT verify the gate conditions itself — those live
    in their own tests. It asserts that we no longer ship a pre-1.0
    marker, so the freeze semantics are explicit.
    """
    v = _pyproject_version()
    major = int(v.split(".")[0])
    assert major >= 1, (
        f"version {v!r} is below 1.0.0 — release gate not yet closed; "
        f"do not bump to 1.0.0 until all P0/P1 findings are resolved."
    )


# Pre-1.0 freeze markers — historical. The set is retained so a
# misbump back to a pre-1.0 marker fails `test_version_is_release_gate`
# above with a clear message instead of silently re-entering freeze.
ACCEPTABLE = {"0.2.1rc1", "0.3.0", "0.3.0.1", "0.4.0", "0.5.0", "0.6.0", "0.6.1"}
ACCEPTABLE_PREFIX = (
    "0.3.0.dev", "0.4.0.dev", "0.5.0.dev", "0.6.0.dev", "0.6.1.dev",
)
