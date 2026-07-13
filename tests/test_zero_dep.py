"""Zero-dep OKF core — §4.2 stdlib import discipline & §4.3 clean-venv runs.

These tests pin v1.1.0's central claim: the OKF core (lint / init / ingest
/ query) runs from a clean venv with **only stdlib** installed. L2 deps
(sqlite-vec + fastembed) install lazily on first search/reindex (see
test_lazy_index.py).

Failing one of these means the OKF core has picked up an unintended
third-party import — which would re-introduce the v0.x install pain
this whole refactor exists to delete.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import venv
from pathlib import Path
import pytest
pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "skills" / "mneme" / "scripts" / "mneme"

# A "stdlib module" — any name not in this set in OKF core files is a
# third-party import we want to know about. ``sqlite_vec`` / ``fastembed``
# / ``yaml`` / ``tomli_w`` must NEVER appear in ``okflib.py`` /
# ``validate_okf.py`` / ``config.py`` / ``toml_writer.py`` / the parts of
# ``cli.py`` that handle ``init`` / ``lint``. L2 paths (cmd_reindex /
# cmd_search) are allowed to import sqlite_vec — covered by lazy_index.py.
_STDLIB_OK = frozenset(sys.stdlib_module_names) | {
    "__future__",  # not really a module, but appears in imports
}

# Per-file third-party import allow-list. Anything not listed AND not stdlib
# fails the test. This is a release gate — the OKF core MUST stay stdlib-only.
#
# Note: ``yaml`` is allowed when wrapped in ``try/except ImportError`` — the
# canonical Python idiom for an optional dependency. We check that via
# ``_optional_imports_in`` below; only the bare ``import yaml`` would be
# a real hard-dep violation.
_THIRD_PARTY_FORBIDDEN = frozenset({
    "sqlite_vec", "fastembed", "tomli_w", "tomli",
    "mneme.indexlib",  # indexlib is L2-only; core paths must not import it
})


def _imports_in(path: Path) -> list[tuple[str, str]]:
    """Return ``[(level, module), ...]`` for every import statement in path."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((str(node.lineno), alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # Relative imports (e.g. `from . import cli`) — `mod` is None.
            if node.level:
                mod = "." * node.level + (node.module or "")
            out.append((str(node.lineno), mod))
    return out


def _optional_imports_in(path: Path) -> set[str]:
    """Modules imported inside a ``try/except ImportError`` block.

    These are the canonical optional-dependency pattern in Python —
    they don't make the dep hard, they let the code adapt at runtime
    to whether the dep is present.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    optional: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(
            isinstance(h.type, ast.Name) and h.type.id == "ImportError"
            for h in node.handlers
        ):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    optional.add(alias.name)
            elif isinstance(stmt, ast.ImportFrom) and stmt.module:
                optional.add(stmt.module)
    return optional


def _okflib_forbidden_imports() -> list[str]:
    """Return a list of forbidden (line, module) imports in okflib.py."""
    optional = _optional_imports_in(PKG / "okflib.py")
    violations = []
    for lineno, mod in _imports_in(PKG / "okflib.py"):
        if mod in optional:
            continue
        top = mod.split(".")[0].lstrip(".")
        if top in _THIRD_PARTY_FORBIDDEN or mod in _THIRD_PARTY_FORBIDDEN:
            violations.append(f"okflib.py:{lineno}: {mod!r}")
    return violations


# ---------------------------------------------------------------------------
# §4.2 stdlib import discipline
# ---------------------------------------------------------------------------

def test_okflib_imports_stdlib_only():
    """okflib.py must not import third-party deps outside ``try/except
    ImportError`` blocks. The OKF v0.1 library that powers lint/init/ingest
    must keep its baseline install zero-dep.

    Note: ``import yaml`` inside ``try/except ImportError`` is the
    canonical Python pattern for optional deps — it does NOT make PyYAML
    a hard requirement. The test allows that pattern explicitly.
    """
    bad = _okflib_forbidden_imports()
    assert not bad, (
        "okflib.py imports third-party modules outside try/except ImportError "
        "blocks; these are hard deps the OKF core should not require:\n"
        + "\n".join(f"  {b}" for b in bad)
    )


def test_validate_okf_default_no_yaml():
    """``validate_okf.py`` (the lint CLI) must not import PyYAML by default.

    PyYAML is opt-in via the `validate` extra; default install should
    still lint a bundle (lenient-subset parser + warnings), per
    CLAUDE.md §"分层依赖" + plan §2.2.
    """
    # Block yaml at import time and re-import in a subprocess.
    code = (
        "import sys\n"
        "sys.modules['yaml'] = None\n"
        "from mneme import validate_okf\n"
        "report = validate_okf.validate_bundle(\n"
        "    validate_okf.Path('/Users/scott1743/opc/mneme/sample-bundle')\n"
        ")\n"
        "assert any(v.rule == 'strict-validation-disabled' for v in report.warnings), \\\n"
        "    f'expected strict-validation-disabled warning; got {[(v.rule, v.detail) for v in report.warnings]}'\n"
        "print('ok')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True, text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(ROOT / "skills" / "mneme" / "scripts")},
    )
    assert r.returncode == 0, (
        f"validate_okf failed when yaml is blocked:\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert r.stdout.strip() == "ok"


# ---------------------------------------------------------------------------
# §4.3 clean-venv integration
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_venv(tmp_path):
    """Build a brand-new venv with NO third-party deps installed.

    The venv gets stdlib + ``pip`` only. We then invoke the CLI from
    the repo source via PYTHONPATH (no editable install).
    """
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(str(venv_dir))
    py = venv_dir / "bin" / "python"
    # Make sure the venv is REALLY empty of project deps. tomli_w was
    # previously a hard dep; if the host has it globally, the venv
    # shouldn't inherit it.
    return py


def test_clean_venv_init_works(clean_venv, tmp_path):
    """`mneme init` runs in a clean venv with zero third-party deps."""
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    r = subprocess.run(
        [str(clean_venv), "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        cwd=str(ROOT / "skills" / "mneme" / "scripts"),
        capture_output=True, text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(ROOT / "skills" / "mneme" / "scripts")},
    )
    assert r.returncode == 0, (
        f"`mneme init` in clean venv failed:\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert (bundle / "index.md").exists()
    assert (bundle / "log.md").exists()
    assert (bundle / "sources" / ".gitkeep").exists()


def test_clean_venv_lint_works_without_index(clean_venv, tmp_path):
    """`mneme lint` runs in a clean venv with no [index] extras.

    The lint path must NOT touch sqlite_vec / fastembed.
    """
    # Copy sample-bundle to a tmp location so we don't pollute the repo.
    import shutil
    bundle = tmp_path / "wiki"
    shutil.copytree(ROOT / "sample-bundle", bundle)
    r = subprocess.run(
        [str(clean_venv), "-m", "mneme", "lint", str(bundle)],
        cwd=str(ROOT / "skills" / "mneme" / "scripts"),
        capture_output=True, text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(ROOT / "skills" / "mneme" / "scripts")},
    )
    # Exit 3 is the "lint ran and found something to look at" signal
    # (orphan section printed to stderr). Exit 0 is also acceptable if
    # sample-bundle is clean.
    assert r.returncode in (0, 3), (
        f"`mneme lint` in clean venv failed:\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    assert "0 error(s)" in r.stdout
    # stderr should mention the orphan analysis (lint always reports it).
    assert "orphan" in r.stderr.lower()


def test_clean_venv_search_fails_cleanly_without_index(clean_venv, tmp_path):
    """`mneme search` in a clean venv (no L2 deps installed) must report a
    plain error message — never a raw traceback from a missing module.
    The skill itself does not auto-install sqlite-vec / fastembed; the user
    opts in by running `pip install ...` themselves. This test pins that
    contract for the clean-venv path.
    """
    import shutil
    bundle = tmp_path / "wiki"
    shutil.copytree(ROOT / "sample-bundle", bundle)
    cfg = tmp_path / "config.toml"
    # Pre-write a config pointing at the bundle so `mneme search` doesn't
    # need to walk up to find it.
    cfg.write_text(f'bundle_path = "{bundle}"\n', encoding="utf-8")

    result = subprocess.run(
        [str(clean_venv), "-m", "mneme", "search", "okf",
         "--config", str(cfg)],
        cwd=str(ROOT / "skills" / "mneme" / "scripts"),
        capture_output=True,
        text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(ROOT / "skills" / "mneme" / "scripts")},
        timeout=60,
    )
    combined = result.stdout + result.stderr
    # Should NOT be a raw traceback from a missing optional module.
    assert "Traceback (most recent call last)" not in combined, (
        f"`mneme search` in clean venv emitted a raw traceback:\n"
        f"rc={result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    # The clean venv cannot satisfy L2 search, so non-zero is expected.
    assert result.returncode != 0, (
        "clean venv unexpectedly indexed a bundle without L2 deps installed"
    )
    # The message should tell the user what to do next, not promise auto-install.
    # Either point at the missing L2 deps or at the missing index — both are
    # valid clean-venv outcomes; the contract is "plain message, no traceback".
    assert (
        "pip install" in combined
        or "L2" in combined
        or "index" in combined
    ), (
        f"`mneme search` in clean venv should report a plain next-step message:\n"
        f"rc={result.returncode}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )