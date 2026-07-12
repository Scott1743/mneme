"""Release-gate guard: a freshly-built `mneme-*.whl` must produce a
working `mneme` console script.

This test catches the bug we hit immediately after tagging v0.3.0:
setuptools generates a console-script stub that calls
`main()` without arguments, so a `[project.scripts] mneme = mneme.cli:main`
entry point only works when the implementation's `main` accepts a
zero-arg call. The v0.3.0 wheel installed cleanly but crashed on every
invocation with `TypeError: main() missing 1 required positional
argument: 'argv'`. The fix (in v0.3.0.1) defaults `argv=None` and falls
back to `sys.argv[1:]`.

This test runs in a brand-new venv so it cannot accidentally rely on
anything in the project's editable install. A wheel that fails this
test cannot ship as the next release.

The test is forgiving about model downloads (it doesn't trigger a
`reindex`). It does exercise `init` and `lint` against an empty bundle
to confirm both code paths through `cli.main` end-to-end.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WHEEL_GLOB = list((ROOT / "dist").glob("mneme-*-py3-none-any.whl"))


def _require_wheel() -> Path:
    if not WHEEL_GLOB:
        pytest.skip(
            "no wheel built; run `python -m build --wheel` first "
            "(test_install.py covers on-demand builds)"
        )
    # Pick the LATEST wheel by version; alphabetical [0] silently picks
    # `mneme-0.5.0` over `mneme-0.6.1` and runs stale code in fresh venvs.
    import re
    def _vkey(name: str):
        m = re.match(r"^mneme-(.+?)-py3-none-any\.whl$", name)
        if not m:
            return ()
        out = []
        for p in m.group(1).split("."):
            d = re.match(r"^(\d+)", p)
            out.append(int(d.group(1)) if d else 0)
        return tuple(out)
    return max(WHEEL_GLOB, key=lambda p: _vkey(p.name))


def _fresh_venv() -> Path:
    base = Path("/tmp") / f"mneme-entrypoint-{sys.version_info.minor}-{id(object())}"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir()
    venv.EnvBuilder(with_pip=True, clear=True).create(str(base))
    return base


def _py(venv_dir: Path) -> str:
    return str(venv_dir / "bin" / "python")


def test_console_script_help_exits_zero():
    """`mneme --help` works in a fresh venv. Catches the v0.3.0
    entry-point argv regression."""
    wheel = _require_wheel()
    env = _fresh_venv()
    try:
        subprocess.run(
            [_py(env), "-m", "pip", "install", "--quiet", str(wheel)],
            check=True, capture_output=True,
        )
        out = subprocess.run(
            [str(env / "bin" / "mneme"), "--help"],
            capture_output=True, text=True,
        )
        assert out.returncode == 0, (
            f"mneme --help failed (rc={out.returncode}); "
            f"stderr: {out.stderr!r}"
        )
        for cmd in ("init", "reindex", "search", "lint"):
            assert cmd in out.stdout, (
                f"`mneme --help` did not list '{cmd}': {out.stdout!r}"
            )
    finally:
        shutil.rmtree(env, ignore_errors=True)


def test_dash_m_mneme_help_in_fresh_venv():
    """`python3 -m mneme --help` works in a fresh venv. Same bug
    surface, different launcher (the package's __main__.py)."""
    wheel = _require_wheel()
    env = _fresh_venv()
    try:
        subprocess.run(
            [_py(env), "-m", "pip", "install", "--quiet", str(wheel)],
            check=True, capture_output=True,
        )
        out = subprocess.run(
            [_py(env), "-m", "mneme", "--help"],
            capture_output=True, text=True,
        )
        assert out.returncode == 0, (
            f"`python3 -m mneme --help` failed (rc={out.returncode}); "
            f"stderr: {out.stderr!r}"
        )
    finally:
        shutil.rmtree(env, ignore_errors=True)


def test_init_then_lint_in_fresh_venv(tmp_path):
    """End-to-end: `mneme init` then `mneme lint` in a brand-new venv.
    Locks in the user-facing sequence that just shipped.
    """
    wheel = _require_wheel()
    env = _fresh_venv()
    cfg = tmp_path / "cfg.toml"
    bundle = tmp_path / "wiki"
    try:
        subprocess.run(
            [_py(env), "-m", "pip", "install", "--quiet", str(wheel)],
            check=True, capture_output=True,
        )
        rc_init = subprocess.run(
            [str(env / "bin" / "mneme"), "init", str(bundle),
             "--config", str(cfg)],
            capture_output=True, text=True,
        )
        assert rc_init.returncode == 0, rc_init.stderr
        assert bundle.is_dir()
        assert (bundle / "index.md").exists()
        assert (bundle / "log.md").exists()
        assert (bundle / "sources").is_dir()
        # `mneme lint` deliberately returns non-zero (the find_orphans
        # guard). That's the right release-shape, but we should still
        # see 0 ERROR on a fresh empty bundle.
        rc_lint = subprocess.run(
            [str(env / "bin" / "mneme"), "lint", str(bundle)],
            capture_output=True, text=True,
        )
        # v0.6.1: find_orphans runs as part of lint. Empty bundle
        # has no concepts, so no orphans fire; lint exits 3 (signal)
        # with an empty orphan section in stderr.
        assert rc_lint.returncode == 3, (
            f"fresh-empty-bundle lint should exit 3; "
            f"got {rc_lint.returncode}"
        )
        assert "orphan concept pages (0)" in rc_lint.stderr
        assert "find_orphans not yet implemented" not in rc_lint.stderr
        assert "0 error(s)" in rc_lint.stdout
    finally:
        shutil.rmtree(env, ignore_errors=True)


def test_wheel_contains_entry_points():
    """The wheel records the `mneme` entry point. Redundant with
    test_install.py::test_wheel_install_provides_entry_point but
    independent so a wheel-build regression doesn't quietly break
    only one of them."""
    wheel = _require_wheel()
    # The dist-info filename includes the version. Find it dynamically.
    with zipfile.ZipFile(wheel) as zf:
        ep_names = [n for n in zf.namelist() if n.endswith("entry_points.txt")]
        assert ep_names, (
            f"wheel {wheel.name} contains no entry_points.txt; "
            f"contents: {zf.namelist()[:10]}"
        )
        ep = zf.read(ep_names[0]).decode("utf-8")
        assert "mneme = mneme.cli:main" in ep, (
            f"wheel entry_points.txt missing `mneme = mneme.cli:main`:\n{ep}"
        )
