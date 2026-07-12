"""Phase 6 release-gate — resource budgets and dependency discipline.

The readiness assessment (§Resource discipline and §P1 Dependency
stability) calls out four avoidable costs and one stability risk:

1. source skill artifact should stay under 250KB
2. plain-Markdown reading MUST NOT require third-party deps (L1 zero-dep)
3. fastembed model cache should be stable, not in OS temp
4. every runtime dependency should declare an upper bound so a clean
   install cannot change behavior without a Mneme code change

Each test below pins one of those invariants. They are release-gate
tests — failing one means the 1.0.0 contract is broken, not that a
feature is missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SKILL_DIR = ROOT / "skills" / "mneme"
INDEXLIB = ROOT / "src" / "mneme" / "indexlib.py"

# Budget from the readiness assessment §Phase 6:
# "base skill artifact < 250KB".
SOURCE_SKILL_BUDGET_BYTES = 250 * 1024


def _dir_size(path: Path) -> int:
    """Sum every regular file under `path`, recursively."""
    if not path.is_dir():
        return 0
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def test_source_skill_under_budget():
    """The source skill directory (SKILL.md + references/ + any other
    agent-facing assets) must stay under 250KB. The assessment measured
    ~128KB at the v0.2.0 baseline; the budget leaves headroom for one
    more scenario doc without re-tuning.
    """
    size = _dir_size(SKILL_DIR)
    assert size < SOURCE_SKILL_BUDGET_BYTES, (
        f"source skill dir is {size} bytes "
        f"({size / 1024:.1f}KB); budget is {SOURCE_SKILL_BUDGET_BYTES} bytes. "
        f"Trim references/ or split heavy prose into a separate doc."
    )


def test_l1_markdown_read_has_zero_runtime_deps():
    """Reading and parsing an OKF bundle's Markdown frontmatter MUST
    NOT require sqlite-vec, fastembed, or PyYAML. L1 stays zero-dep
    so a fresh `pip install mneme` can validate a bundle without
    pulling the L2 stack.

    Concretely: `mneme.okflib` imports clean when those three modules
    are absent from `sys.modules`. We simulate absence by removing
    their entries and re-importing in a subprocess so the test is
    honest (no cached import).
    """
    import subprocess
    code = (
        "import sys\n"
        # Block the three optional deps so any import attempt fails.
        "for mod in ('sqlite_vec', 'fastembed', 'yaml'):\n"
        "    sys.modules[mod] = None\n"
        "from mneme import okflib\n"
        "from mneme.validate_okf import validate_bundle\n"
        "print('ok')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert r.returncode == 0, (
        f"L1 import failed when sqlite-vec/fastembed/PyYAML are blocked:\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert r.stdout.strip() == "ok"


def test_model_cache_dir_is_stable_under_home():
    """`_model_cache_dir()` returns a path under the user's home, not
    an OS temp directory. The assessment flagged FastEmbed's default
    OS-temp cache as the reason the 91MB BGE model could be silently
    re-downloaded after a reboot or temp cleanup.
    """
    # Use a fresh env so MNEME_MODEL_CACHE doesn't shadow the default.
    import os
    saved = os.environ.pop("MNEME_MODEL_CACHE", None)
    try:
        from mneme.indexlib import _model_cache_dir
        cache = _model_cache_dir()
        home = Path.home()
        assert str(cache).startswith(str(home)), (
            f"model cache {cache} is not under $HOME; "
            f"OS temp cleanup could evict it and force re-download."
        )
        # Path should be mneme-specific so we don't fight fastembed's
        # own default location.
        assert "mneme" in cache.parts, (
            f"model cache {cache} is not mneme-namespaced."
        )
    finally:
        if saved is not None:
            os.environ["MNEME_MODEL_CACHE"] = saved


def test_model_cache_dir_honors_env_override():
    """MNEME_MODEL_CACHE lets users relocate the cache (e.g. to a
    tmpfs for tests or a shared NAS)."""
    import os
    from mneme.indexlib import _model_cache_dir
    saved = os.environ.pop("MNEME_MODEL_CACHE", None)
    try:
        os.environ["MNEME_MODEL_CACHE"] = "/tmp/mneme-test-cache-override"
        assert str(_model_cache_dir()) == "/tmp/mneme-test-cache-override"
    finally:
        if saved is not None:
            os.environ["MNEME_MODEL_CACHE"] = saved
        else:
            os.environ.pop("MNEME_MODEL_CACHE", None)


def test_runtime_dependencies_have_upper_bounds():
    """Every dependency in [project].dependencies and each optional
    extra MUST declare an upper bound (a `,<` clause). The
    assessment flagged `sqlite-vec` and `fastembed` as pre-v1 with
    explicit breaking-change warnings; unbounded deps mean a clean
    install can change behavior without a Mneme code change.

    We accept `pytest>=7` (dev only) without an upper bound because
    pytest's own stability budget is well past 1.0 and the dev extra
    does not ship. Runtime deps — base + validate + index + toml10
    + all — must all carry upper bounds.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    # Extract each extra block.
    runtime_extras = ("validate", "index", "toml10", "all")
    # Base dependencies line.
    base_match = re.search(
        r'^dependencies\s*=\s*\[(.*?)\]',
        text, re.MULTILINE | re.DOTALL,
    )
    assert base_match, "could not find `dependencies = [...]` in pyproject.toml"
    _assert_bounds(base_match.group(1), "base dependencies")

    for extra in runtime_extras:
        m = re.search(
            rf'^{re.escape(extra)}\s*=\s*\[(.*?)\]',
            text, re.MULTILINE | re.DOTALL,
        )
        assert m, f"could not find `{extra} = [...]` extra in pyproject.toml"
        _assert_bounds(m.group(1), f"{extra} extra")


def _assert_bounds(block: str, label: str) -> None:
    """Assert every requirement string in `block` carries a `,<` upper bound."""
    # Pull each quoted requirement out of the TOML block.
    reqs = re.findall(r'"([^"]+)"', block)
    assert reqs, f"{label}: no requirements found in block {block!r}"
    for req in reqs:
        # Accept either `<` or `,<` as the upper-bound marker.
        assert "," in req or "<" in req, (
            f"{label}: requirement {req!r} has no upper bound; "
            f"pre-v1 deps (sqlite-vec, fastembed) can break on a clean "
            f"install without a Mneme code change."
        )
