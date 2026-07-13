import json
from pathlib import Path

from mneme import indexlib
import mneme
import pytest
pytestmark = pytest.mark.unit


def test_init_scaffolds_bundle_and_config(tmp_path):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "mywiki"
    rc = mneme.main(["init", str(bundle), "--config", str(cfg)])
    assert rc == 0
    assert (bundle / "index.md").exists()
    assert (bundle / "log.md").exists()
    assert (bundle / "sources").is_dir()
    assert "okf_version" in (bundle / "index.md").read_text()
    assert f'bundle_path = "{bundle}"' in cfg.read_text()


def test_reindex_reports_structured_counts(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    result = indexlib.ReindexResult(2, 4, 1, bundle / ".mneme" / "index.db")
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: object())
    monkeypatch.setattr(indexlib, "reindex_bundle", lambda *_args, **_kwargs: result)
    assert mneme.main(["reindex", "--config", str(cfg)]) == 0
    assert "2 concepts / 4 chunks (1 skipped)" in capsys.readouterr().out


def _search_candidate(query):
    """Sample v2.0 candidate shape returned by the FTS5 path."""
    return {
        "path": "concepts/a.md",
        "title": "中文 A",
        "snippet": f"中文 A {query}",
    }


def test_search_json_is_stable_and_passes_query_as_data(tmp_path, monkeypatch, capsys):
    """v2.0 search JSON shape: ``{"query": ..., "candidates": [...]}``,
    each candidate carries ``path``, ``title``, ``snippet``.
    """
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    query = "引号 ' \" newline\n$()"
    seen = {}

    def fake_search(query, db, k):
        seen.update(query=query, db=str(db), k=k)
        return {"query": query, "candidates": [_search_candidate(query)]}

    monkeypatch.setattr(indexlib, "search", fake_search)
    # Drop a sentinel index.db so cmd_search takes the FTS5 path
    # rather than the L0 grep fallback.
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_bytes(b"")
    rc = mneme.main(["search", query, "-k", "5", "--json", "--config", str(cfg)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert seen["query"] == query
    assert seen["k"] == 5
    assert payload["query"] == query
    assert payload["candidates"][0]["path"] == "concepts/a.md"
    assert payload["candidates"][0]["title"] == "中文 A"


def test_search_human_output(tmp_path, monkeypatch, capsys):
    """v2.0 human output is tab-separated ``path\\ttitle\\tsnippet``
    lines — one per candidate.
    """
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    monkeypatch.setattr(
        indexlib,
        "search",
        lambda query, db, k: {"query": query, "candidates": [_search_candidate("body")]},
    )
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_bytes(b"")
    assert mneme.main(["search", "body", "--config", str(cfg)]) == 0
    output = capsys.readouterr().out
    assert "concepts/a.md" in output
    assert "中文 A" in output
    assert "body" in output


def test_search_zero_hits_is_success(tmp_path, monkeypatch, capsys):
    """Empty candidates still exit 0 and emit the new JSON shape."""
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    monkeypatch.setattr(
        indexlib, "search", lambda query, db, k: {"query": query, "candidates": []}
    )
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_bytes(b"")
    assert mneme.main(["search", "none", "--json", "--config", str(cfg)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"query": "none", "candidates": []}


def test_search_runtime_error_returns_1(tmp_path, monkeypatch, capsys):
    """FTS5 errors propagate as exit 1 with the underlying message."""
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    (bundle / ".mneme").mkdir()
    (bundle / ".mneme" / "index.db").write_bytes(b"")

    def fail(*_args, **_kwargs):
        raise RuntimeError("index metadata is missing; run mneme reindex")

    monkeypatch.setattr(indexlib, "search", fail)
    assert mneme.main(["search", "x", "--config", str(cfg)]) == 1
    assert "run mneme reindex" in capsys.readouterr().err


def test_usage_errors_return_2():
    assert mneme.main([]) == 2
    assert mneme.main(["bogus"]) == 2
    assert mneme.main(["search"]) == 2
    assert mneme.main(["search", "   "]) == 2
    assert mneme.main(["search", "x", "-k", "0"]) == 2


def test_cli_no_apply_flag_on_dream():
    """Pre-Task B frozen contract: `mneme dream` is read-only audit and
    never exposes a write flag.  Calling `mneme dream` always exits 0.
    """
    assert mneme.main(["dream", "--bundle", "/nonexistent"]) == 0


def test_cli_lint_runs_find_orphans(tmp_path, capsys):
    """Pre-Task B: `mneme lint --bundle <path>` runs the OKF validator
    and the `find_orphans` primitive. The fixture bundle has one
    concept with no inbound edge, so find_orphans surfaces a real
    orphan section. Lint exits 0 when the bundle has no OKF errors.
    """
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Test\n')
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "a.md").write_text(
        '---\ntype: Concept\ntitle: A\ntags: [a]\n---\n\nbody\n'
    )
    rc = mneme.main(["lint", "--bundle", str(bundle)])
    captured = capsys.readouterr()
    assert rc == 0
    # The orphan is now surfaced as a real section.
    assert "orphan concept pages" in captured.err
    assert "concepts/a" in captured.err, (
        f"expected concepts/a listed as orphan; stderr={captured.err!r}"
    )
    # Regression guard for the v0.3.0 freeze message.
    assert "find_orphans not yet implemented" not in captured.err, (
        f"lint re-emitted the unimplemented guard; stderr={captured.err!r}"
    )
