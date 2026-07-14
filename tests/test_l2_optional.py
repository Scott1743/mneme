"""v3.0 --l2 opt-in flag — surface contract.

v3.0 introduces L2 (sqlite-vec + FastEmbed + BGE-small-zh-v1.5)
as an **explicit opt-in** flag on `reindex` and `search`. The FTS5
default path stays untouched. These tests pin:

  1. ``mneme reindex --help`` advertises ``--l2``.
  2. ``mneme search --help`` advertises ``--l2``.
  3. ``mneme search --l2`` against an FTS5-only index errors out
     with a clear, single-line hint on stderr — NOT a raw
     ``ImportError`` traceback from a missing sqlite-vec / fastembed
     module. The CLI must never silently fall back to FTS5 when
     ``--l2`` was explicit.

Marked ``@pytest.mark.l2`` and registered in ``pyproject.toml`` so
default runs (``pytest -m "not l2 and not network"``) skip them and
release pipelines can opt in via ``pytest -m l2``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.l2

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "skills" / "mneme" / "scripts"


def _run_cli(*argv: str) -> subprocess.CompletedProcess:
    """Invoke ``python -m mneme <argv>`` from the skills/mneme/scripts cwd."""
    return subprocess.run(
        [sys.executable, "-m", "mneme", *argv],
        cwd=str(PKG_ROOT),
        capture_output=True,
        text=True,
        env={**__import__("os").environ,
             "PYTHONPATH": str(PKG_ROOT)},
        timeout=30,
    )


# ---------------------------------------------------------------------------
# CLI surface — --l2 must be a registered flag on both subcommands.
# ---------------------------------------------------------------------------


def test_reindex_help_advertises_l2_flag() -> None:
    """`mneme reindex --help` must mention ``--l2``."""
    r = _run_cli("reindex", "--help")
    # argparse exits 0 on --help; the L2 flag's `help=` string is what we
    # grep for. We don't pin the help text body (that's a documentation
    # concern), only that the flag is registered.
    assert r.returncode == 0, (
        f"`mneme reindex --help` exited {r.returncode}: "
        f"stdout={r.stdout!r} stderr={r.stderr!r}"
    )
    assert "--l2" in r.stdout, (
        f"`mneme reindex --help` does not advertise `--l2`; "
        f"stdout={r.stdout!r}"
    )


def test_search_help_advertises_l2_flag() -> None:
    """`mneme search --help` must mention ``--l2``."""
    r = _run_cli("search", "--help")
    assert r.returncode == 0, (
        f"`mneme search --help` exited {r.returncode}: "
        f"stdout={r.stdout!r} stderr={r.stderr!r}"
    )
    assert "--l2" in r.stdout, (
        f"`mneme search --help` does not advertise `--l2`; "
        f"stdout={r.stdout!r}"
    )


def _l2_help_block(stdout: str) -> str:
    """Return the multi-line ``--l2  <help text>`` block from --help.

    argparse prints the usage line first (with `--l2]` literally in the
    options list) and then the indented help block as separate lines.
    We want the latter. The help block is everything from the first
    line that starts (after optional whitespace) with ``--l2`` up to
    the next blank line.
    """
    lines = stdout.splitlines()
    capture: list[str] = []
    started = False
    for line in lines:
        stripped = line.lstrip()
        if not started:
            if stripped.startswith("--l2"):
                started = True
                # Drop the leading whitespace + ``--l2`` flag token, keep
                # the rest of the line and any continuation lines.
                capture.append(stripped.split("--l2", 1)[1].strip())
        else:
            if not line.strip():
                break
            capture.append(line.strip())
    return " ".join(capture)


def test_reindex_help_l2_mentions_required_packages() -> None:
    """The ``--l2`` flag help text should advertise the pip-install hint
    so a user who runs ``mneme reindex --help`` learns the dependency
    shape up front."""
    r = _run_cli("reindex", "--help")
    assert r.returncode == 0
    block = _l2_help_block(r.stdout)
    assert block, (
        f"could not find --l2 help block in reindex --help; "
        f"stdout={r.stdout!r}"
    )
    text = block.lower()
    assert "sqlite-vec" in text or "fastembed" in text, (
        f"`--l2` help text should mention required packages; got {block!r}"
    )


def test_search_help_l2_warns_about_silent_fallback() -> None:
    """The ``--l2`` flag help text must explicitly warn that ``--l2``
    refuses to silently fall back to FTS5 — that contract is what
    distinguishes v2.1's explicit opt-in from a v0.x silent default."""
    r = _run_cli("search", "--help")
    assert r.returncode == 0
    block = _l2_help_block(r.stdout)
    assert block, (
        f"could not find --l2 help block in search --help; "
        f"stdout={r.stdout!r}"
    )
    text = block.lower()
    assert "fts5" in text or "fall back" in text or "silent" in text, (
        f"`--l2` help text on `search` should warn about FTS5 fallback; "
        f"got {block!r}"
    )


# ---------------------------------------------------------------------------
# Behaviour — --l2 must NOT silently fall back to FTS5.
# ---------------------------------------------------------------------------


def _make_fts5_only_bundle(tmp_path: Path) -> tuple[Path, Path]:
    """Build a bundle + an FTS5-only index.db (no vec_chunks table)."""
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg = tmp_path / "config.toml"
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    (bundle / "sources").mkdir()
    (bundle / "sources" / ".gitkeep").touch()
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "a.md").write_text(
        '---\ntype: Concept\ntitle: A\ntags: [a]\n---\n\nbody\n',
        encoding="utf-8",
    )
    # Run a real reindex so the FTS5 schema is on disk. This goes
    # through the default (non-L2) path; vec_chunks must NOT exist.
    rc = subprocess.run(
        [sys.executable, "-m", "mneme", "reindex",
         "--bundle", str(bundle), "--config", str(cfg)],
        cwd=str(PKG_ROOT),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(PKG_ROOT)},
        timeout=30,
    )
    assert rc.returncode == 0, (
        f"baseline reindex (FTS5) failed: rc={rc.returncode} "
        f"stdout={rc.stdout!r} stderr={rc.stderr!r}"
    )
    import sqlite3
    db = bundle / ".mneme" / "index.db"
    with sqlite3.connect(str(db)) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='vec_chunks'"
        ).fetchone()
    assert row is None, (
        "baseline FTS5 reindex unexpectedly created vec_chunks; "
        "FTS5 must be sqlite-vec-free"
    )
    return bundle, cfg


def test_search_l2_on_fts5_index_errors_cleanly(tmp_path) -> None:
    """`mneme search --l2` against an FTS5-only index must error with a
    one-line stderr hint and a non-zero exit — never an ImportError
    traceback, never a silent FTS5 fallback."""
    bundle, cfg = _make_fts5_only_bundle(tmp_path)

    r = _run_cli(
        "search", "anything", "--l2", "--bundle", str(bundle), "--config", str(cfg),
    )

    combined = r.stdout + r.stderr
    # No raw traceback — that is the original zero-dep contract, and it
    # must hold for `--l2` as well.
    assert "Traceback (most recent call last)" not in combined, (
        f"`mneme search --l2` on FTS5 index emitted a raw traceback:\n"
        f"rc={r.returncode}\nstdout={r.stdout!r}\nstderr={r.stderr!r}"
    )
    # No silent fallback — exit must be non-zero so callers (agents,
    # shell scripts) learn that --l2 was not honored.
    assert r.returncode != 0, (
        f"`mneme search --l2` against FTS5-only index exited 0; "
        f"--l2 must NOT silently fall back. stdout={r.stdout!r} "
        f"stderr={r.stderr!r}"
    )
    # The hint must mention `--l2` (the user's request) and the remedy
    # (run `mneme reindex --l2` first). We accept either "reindex --l2"
    # or "no vec_chunks" / "FTS5-only" wording.
    assert "reindex --l2" in r.stderr or "vec_chunks" in r.stderr, (
        f"`mneme search --l2` stderr should explain the remedy; "
        f"got stderr={r.stderr!r}"
    )
    # And the stderr should NOT mention the install hint — the issue
    # here isn't a missing package, it's an FTS5 index. The install
    # hint is reserved for the missing-package branch (FastEmbedUnavailable
    # / SqliteVecUnavailable).
    assert "pip install" not in r.stderr or "reindex --l2" in r.stderr, (
        f"`mneme search --l2` on FTS5 index should not just print "
        f"`pip install ...`; got stderr={r.stderr!r}"
    )


def test_search_l2_with_no_index_at_all_errors_cleanly(tmp_path) -> None:
    """`mneme search --l2` against a bundle with no index.db must also
    error with the same clear hint — never traceback, never fallback."""
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg = tmp_path / "config.toml"
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
    )
    (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")

    r = _run_cli(
        "search", "x", "--l2", "--bundle", str(bundle), "--config", str(cfg),
    )

    combined = r.stdout + r.stderr
    assert "Traceback (most recent call last)" not in combined, (
        f"`mneme search --l2` with no index emitted a raw traceback:\n"
        f"rc={r.returncode}\nstdout={r.stdout!r}stderr={r.stderr!r}"
    )
    assert r.returncode != 0, (
        f"`mneme search --l2` with no index exited 0; "
        f"stdout={r.stdout!r} stderr={r.stderr!r}"
    )
    assert "reindex --l2" in r.stderr, (
        f"`mneme search --l2` with no index should mention "
        f"`mneme reindex --l2`; got stderr={r.stderr!r}"
    )


def test_reindex_l2_missing_deps_gives_one_line_hint(tmp_path, monkeypatch) -> None:
    """`mneme reindex --l2` when sqlite-vec / fastembed are NOT installed
    must print a single-line install hint on stderr — not an
    ImportError traceback. We monkeypatch ``indexlib.default_embed_fn``
    to simulate the missing-deps branch deterministically (no need to
    actually uninstall fastembed in CI)."""
    from mneme import cli, indexlib

    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')

    def _no_fastembed():
        raise indexlib.FastEmbedUnavailableError(
            "fastembed is required for semantic indexing/search. "
            "Install once with: pip install 'fastembed>=0.8.0,<0.9'"
        )

    monkeypatch.setattr(indexlib, "default_embed_fn", _no_fastembed)
    rc = cli.main(["reindex", "--l2", "--config", str(cfg)])
    assert rc == 1, (
        f"`mneme reindex --l2` with missing fastembed should exit 1; "
        f"got rc={rc}"
    )

    import io
    import contextlib

    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        rc = cli.main(["reindex", "--l2", "--config", str(cfg)])
    stderr_text = captured.getvalue()
    assert rc == 1
    assert "Traceback (most recent call last)" not in stderr_text, (
        f"`mneme reindex --l2` with missing deps emitted a raw traceback: "
        f"stderr={stderr_text!r}"
    )
    assert "pip install" in stderr_text, (
        f"`mneme reindex --l2` missing-deps stderr should advertise the "
        f"install command; got stderr={stderr_text!r}"
    )


def test_search_l2_missing_deps_gives_one_line_hint(tmp_path, monkeypatch) -> None:
    """Mirror of the reindex test: `mneme search --l2` with a vec_chunks
    index present but fastembed missing must print the install hint,
    not an ImportError traceback.

    We can't hand-craft a real ``vec_chunks`` table without the
    sqlite-vec module loaded, so we monkeypatch ``indexlib.search_bundle``
    to raise :class:`FastEmbedUnavailableError` directly — the same
    exception path the CLI catches when the real embedder init fails.
    The ``vec_chunks``-present precondition is tested separately by
    :func:`test_search_l2_on_fts5_index_errors_cleanly`.
    """
    from mneme import cli, indexlib

    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text(
        '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
    )
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    (bundle / ".mneme").mkdir()
    # Even an empty index.db makes the ``db.is_file()`` check pass. The
    # sqlite_master lookup will return no vec_chunks row, so the CLI
    # would normally take the "FTS5-only" branch. To exercise the
    # FastEmbedUnavailableError branch we also stub ``search_bundle``
    # AND mark the vec_chunks lookup as present (we inject a fake
    # ``sqlite_master`` row via a monkeypatch on the lookup helper).

    # Monkeypatch the in-line sqlite_master lookup inside cmd_search
    # by monkeypatching ``_has_vec`` via the search_bundle stub: we make
    # ``default_embed_fn`` succeed (it's only the second call from
    # search_bundle that raises) and short-circuit the vec_chunks check
    # by replacing the search_bundle call path. Simpler: monkeypatch
    # both ``default_embed_fn`` (raise) and the inline vec_chunks check
    # is bypassed by calling ``search_bundle`` directly via the patched
    # ``default_embed_fn`` path. We instead monkeypatch the entire
    # search_bundle to raise immediately, mimicking the case where the
    # CLI has progressed past the vec_chunks check.
    def _no_fastembed_search_bundle(*args, **kwargs):
        raise indexlib.FastEmbedUnavailableError(
            "fastembed is required for semantic indexing/search. "
            "Install once with: pip install 'fastembed>=0.8.0,<0.9'"
        )

    monkeypatch.setattr(indexlib, "search_bundle", _no_fastembed_search_bundle)

    # The CLI's inline vec_chunks check will look up
    # ``SELECT 1 FROM sqlite_master WHERE name='vec_chunks'`` and find
    # nothing on this empty db, taking the "FTS5-only" branch instead
    # of the FastEmbed branch. To exercise the FastEmbed branch we
    # also stub ``default_embed_fn`` AND inject a fake vec_chunks
    # sentinel by creating a regular table of that name (sqlite_master
    # doesn't care whether it's virtual or not).
    import sqlite3
    db = bundle / ".mneme" / "index.db"
    with sqlite3.connect(str(db)) as conn:
        # A plain table named vec_chunks (not vec0) is enough to make
        # the CLI's sqlite_master lookup succeed; the actual vector
        # table never gets queried because search_bundle raises first.
        conn.execute(
            "CREATE TABLE vec_chunks ("
            "chunk_id INTEGER PRIMARY KEY, embedding BLOB)"
        )
        conn.commit()

    def _no_fastembed():
        raise indexlib.FastEmbedUnavailableError(
            "fastembed is required for semantic indexing/search. "
            "Install once with: pip install 'fastembed>=0.8.0,<0.9'"
        )

    monkeypatch.setattr(indexlib, "default_embed_fn", _no_fastembed)
    import contextlib
    import io

    captured_err = io.StringIO()
    with contextlib.redirect_stderr(captured_err):
        rc = cli.main(["search", "x", "--l2", "--config", str(cfg)])
    stderr_text = captured_err.getvalue()

    assert rc == 1, (
        f"`mneme search --l2` with missing fastembed should exit 1; "
        f"got rc={rc}; stderr={stderr_text!r}"
    )
    assert "Traceback (most recent call last)" not in stderr_text, (
        f"`mneme search --l2` missing-deps emitted a raw traceback: "
        f"stderr={stderr_text!r}"
    )
    assert "pip install" in stderr_text, (
        f"`mneme search --l2` missing-deps stderr should advertise the "
        f"install command; got stderr={stderr_text!r}"
    )


def test_default_search_still_uses_fts5_when_index_present(tmp_path) -> None:
    """Sanity check that v2.1's default search path is still FTS5 — the
    whole point of the explicit ``--l2`` opt-in is that omitting it does
    NOT touch vec_chunks / sqlite-vec / fastembed."""
    bundle, cfg = _make_fts5_only_bundle(tmp_path)
    r = _run_cli(
        "search", "body", "--bundle", str(bundle), "--config", str(cfg),
    )
    assert r.returncode == 0, (
        f"`mneme search` (default, no --l2) on FTS5 index failed: "
        f"rc={r.returncode} stdout={r.stdout!r} stderr={r.stderr!r}"
    )
    # The FTS5 path returns the matched concept path. We don't pin the
    # exact body column match — FTS5 tokenization is "body" → "body"
    # trivially — but the FTS5 result must surface the concepts/a.md
    # file we ingested.
    assert "concepts/a.md" in r.stdout, (
        f"default `mneme search` should surface FTS5 hit on concepts/a.md; "
        f"stdout={r.stdout!r}"
    )
