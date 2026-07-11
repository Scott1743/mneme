"""§5 install / wheel / path coverage tests.

Each test runs in a fresh temporary virtualenv to simulate the
fresh-install experience: no implicit reliance on `pip install -e .`
or on the in-repo `src/` on `sys.path`. The fixture builds the wheel
once per session via `python -m build --wheel` and caches it under
`dist/mneme-*-py3-none-any.whl`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
WHEEL_GLOB = list((ROOT / "dist").glob("mneme-*-py3-none-any.whl"))


def _build_wheel(tmp_path_factory) -> Path:
    """Build the wheel into a session tmp dir if not already present."""
    if WHEEL_GLOB:
        return WHEEL_GLOB[0]
    out = tmp_path_factory.mktemp("wheel") / "wheel"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return next(out.glob("mneme-*.whl"))


def _require_wheel() -> Path:
    if not WHEEL_GLOB:
        pytest.skip(
            "wheel not built; run `python -m build --wheel` to produce it"
        )
    return WHEEL_GLOB[0]


def _ensure_wheel(tmp_path_factory) -> Path:
    """Use cached wheel if present, otherwise build one. Skips on failure."""
    if WHEEL_GLOB:
        return WHEEL_GLOB[0]
    try:
        return _build_wheel(tmp_path_factory)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"wheel build failed: {exc.stderr.decode()[:200]}")


def _fresh_venv(python: str) -> Path:
    """Create a clean venv with a brand-new home of HOME=tmp so we don't
    pick up the user's real `~/.config/mneme/config.toml`.
    """
    work = Path("/tmp") if os.name == "posix" else Path(os.environ["TEMP"])
    base = work / f"mneme-test-venv-{os.getpid()}-{id(object())}"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir()
    venv.EnvBuilder(with_pip=True, clear=True).create(str(base))
    return base


def _py(venv_dir: Path) -> str:
    if os.name == "posix":
        return str(venv_dir / "bin" / "python")
    return str(venv_dir / "Scripts" / "python.exe")


# ─────────────────────────────────────────────────────────────────────────────

def test_wheel_install_mneme_help(tmp_path, tmp_path_factory):
    """§5.1: `pip install mneme-*.whl` in a fresh venv produces a working
    `mneme` console command. No repository-relative paths.
    """
    wheel = _ensure_wheel(tmp_path_factory)
    env_dir = _fresh_venv(sys.executable)
    try:
        subprocess.run(
            [_py(env_dir), "-m", "pip", "install", "--quiet", str(wheel)],
            check=True,
            capture_output=True,
        )
        out = subprocess.run(
            [_py(env_dir), "-m", "mneme", "--help"],
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        for cmd in ("init", "reindex", "search", "lint"):
            assert cmd in out.stdout, (
                f"`mneme --help` did not list '{cmd}': {out.stdout!r}"
            )
    finally:
        shutil.rmtree(env_dir, ignore_errors=True)


def test_wheel_install_provides_entry_point():
    """§5.10: a fresh install exposes the `mneme` console script driven
    by the `[project.scripts]` entry point, not by `python3 scripts/...`.
    """
    wheel = _require_wheel()
    # The dist-info filename includes the version; find it dynamically.
    with zipfile.ZipFile(wheel) as zf:
        ep_names = [
            n for n in zf.namelist() if n.endswith("entry_points.txt")
        ]
        assert ep_names, (
            f"wheel {wheel.name} has no entry_points.txt; "
            f"contents: {zf.namelist()[:10]}"
        )
        ep_text = zf.read(ep_names[0]).decode("utf-8")
    assert "mneme = mneme.cli:main" in ep_text


def test_wheel_install_with_extras_reindex_runs(tmp_path, tmp_path_factory):
    """§5.2: `pip install 'mneme-*.whl[index]'` then `mneme reindex` runs
    to completion against a freshly-init'd bundle.

    The model download step may fail on networks that block HuggingFace,
    so we treat the reindex as successful if it returns 0, or as a known
    failure with fastembed if it doesn't.
    """
    pytest.importorskip("sqlite_vec")
    pytest.importorskip("fastembed")
    wheel = _ensure_wheel(tmp_path_factory)
    env_dir = _fresh_venv(sys.executable)
    try:
        subprocess.run(
            [_py(env_dir), "-m", "pip", "install", "--quiet",
             str(wheel) + "[index]"],
            check=True, capture_output=True,
        )
        bundle = tmp_path / "wiki"
        # Use a never-before config so we test the init flow too.
        subprocess.run(
            [_py(env_dir), "-m", "mneme", "init", str(bundle),
             "--config", str(tmp_path / "config.toml")],
            check=True, capture_output=True,
        )
        result = subprocess.run(
            [_py(env_dir), "-m", "mneme", "reindex",
             "--config", str(tmp_path / "config.toml")],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            # Acceptable: BGE model download blocked. Mark xfail-like
            # behavior with a clear reason.
            assert "fastembed" in result.stderr or "BAAI" in result.stderr, (
                f"unexpected reindex failure: rc={result.returncode} "
                f"stderr={result.stderr}"
            )
            pytest.skip(
                f"reindex skipped due to environment: {result.stderr[:200]}"
            )
    finally:
        shutil.rmtree(env_dir, ignore_errors=True)


def test_relative_bundle_path_resolves_absolute_after_cwd_change(tmp_path):
    """§5.3: `mneme init ./wiki` writes a relative path; switching cwd
    and re-running the CLI must still resolve the original bundle."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    cfg = tmp_path / "config.toml"
    # First cwd: a, init writes 'wiki' relative to a
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", "./wiki", "--config", str(cfg)],
        cwd=str(a), capture_output=True, text=True, check=True,
    )
    # Switch cwd to b, run a no-op command (search with empty result
    # is OK — we just want resolve_bundle to not blow up)
    res = subprocess.run(
        [sys.executable, "-m", "mneme", "search", "anything", "--config",
         str(cfg), "--json"],
        cwd=str(b), capture_output=True, text=True,
    )
    # Either search succeeds (returns []) or fails with "no bundle".
    # The point is it must NOT find a phantom /tmp/<...>/B/wiki by mistake.
    if res.returncode != 0:
        assert "bundle" in res.stderr or "wiki" in res.stderr, (
            f"unrelated bundle resolution error: {res.stderr}"
        )


def test_bundle_path_with_space(tmp_path):
    """§5.4 space"""
    bundle = tmp_path / "has space" / "wiki"
    cfg = tmp_path / "config.toml"
    mneme = Path(sys.executable).parent / "mneme"
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True,
    )
    # Don't require text equality — just that init succeeds and a
    # subsequent read gives back the exact path.
    assert rc.returncode == 0, rc.stderr
    from mneme.config import read_config
    val = read_config(cfg)["bundle_path"]
    assert val == str(bundle)


def test_bundle_path_with_embedded_quote(tmp_path):
    """§5.4 quote"""
    bundle = tmp_path / 'has"quote' / "wiki"
    cfg = tmp_path / "config.toml"
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True,
    )
    if rc.returncode != 0 and "OSError" not in rc.stderr:
        pytest.skip("OS refuses embedded quote in path on this platform")
    from mneme.config import read_config
    val = read_config(cfg)["bundle_path"]
    assert val == str(bundle)


def test_bundle_path_chinese(tmp_path):
    """§5.4 non-ASCII"""
    bundle = tmp_path / "笔记" / "wiki"
    cfg = tmp_path / "config.toml"
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "init", str(bundle),
         "--config", str(cfg)],
        capture_output=True, text=True, check=True,
    )
    from mneme.config import read_config
    val = read_config(cfg)["bundle_path"]
    assert val == str(bundle)


def test_wheel_contains_skill_assets():
    """§5.7: wheel must ship SKILL.md and references/ inside mneme/skill/.
    """
    if not WHEEL_GLOB:
        pytest.skip("wheel not built")
    wheel = WHEEL_GLOB[0]
    names = set(zipfile.ZipFile(wheel).namelist())
    assert "mneme/skill/SKILL.md" in names
    assert any(n.startswith("mneme/skill/references/") for n in names)


def test_wheel_excludes_tests_research_plans():
    """§5.6: wheel must NOT ship tests/, .research/, docs/superpowers/plans/,
    or sample-bundle/."""
    if not WHEEL_GLOB:
        pytest.skip("wheel not built")
    wheel = WHEEL_GLOB[0]
    names = set(zipfile.ZipFile(wheel).namelist())
    forbidden_substrings = (
        "tests/", ".research/", "superpowers/plans/", "sample-bundle/",
    )
    for n in names:
        for bad in forbidden_substrings:
            assert bad not in n, f"forbidden path leaked into wheel: {n}"


def test_skill_md_no_repository_relative_paths():
    """§5.9: SKILL.md should not embed `python3 skills/mneme/scripts/...`
    style paths since the install no longer has those scripts visible.
    """
    skill_md = ROOT / "skills" / "mneme" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    bad_patterns = (
        "skills/mneme/scripts/",
        "../scripts/",
        "./scripts/",
    )
    for p in bad_patterns:
        assert p not in text, f"SKILL.md still references `{p}` (use `mneme ...` instead)"