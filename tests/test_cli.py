import json
from pathlib import Path

from mneme import indexlib
import mneme


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


def _search_hit(query):
    return {
        "concept_id": "concepts/a",
        "path": "concepts/a.md",
        "title": "中文 A",
        "type": "WhateverThing",
        "text": f"# 中文 A\n{query}",
        "distance": 0.125,
    }


def test_search_json_is_stable_and_passes_query_as_data(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    query = "引号 ' \" newline\n$()"
    seen = {}

    def fake_search(bundle_path, value, k, concept_type):
        seen.update(bundle=bundle_path, query=value, k=k, concept_type=concept_type)
        return [_search_hit(value)]

    monkeypatch.setattr(indexlib, "search_bundle", fake_search)
    rc = mneme.main(
        ["search", query, "-k", "5", "--type", "WhateverThing", "--json", "--config", str(cfg)]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert seen == {
        "bundle": bundle,
        "query": query,
        "k": 5,
        "concept_type": "WhateverThing",
    }
    assert payload[0]["rank"] == 1
    assert payload[0]["path"] == "concepts/a.md"
    assert payload[0]["title"] == "中文 A"


def test_search_human_output(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    monkeypatch.setattr(indexlib, "search_bundle", lambda *_args, **_kwargs: [_search_hit("body")])
    assert mneme.main(["search", "body", "--config", str(cfg)]) == 0
    output = capsys.readouterr().out
    assert "1. 中文 A [WhateverThing]" in output
    assert "concepts/a.md  distance=0.1250" in output


def test_search_zero_hits_is_success(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')
    monkeypatch.setattr(indexlib, "search_bundle", lambda *_args, **_kwargs: [])
    assert mneme.main(["search", "none", "--json", "--config", str(cfg)]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_search_runtime_error_returns_1(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    cfg.write_text(f'bundle_path = "{bundle}"\n')

    def fail(*_args, **_kwargs):
        raise indexlib.IndexNotFoundError("run mneme reindex")

    monkeypatch.setattr(indexlib, "search_bundle", fail)
    assert mneme.main(["search", "x", "--config", str(cfg)]) == 1
    assert "run mneme reindex" in capsys.readouterr().err


def test_usage_errors_return_2():
    assert mneme.main([]) == 2
    assert mneme.main(["bogus"]) == 2
    assert mneme.main(["search"]) == 2
    assert mneme.main(["search", "   "]) == 2
    assert mneme.main(["search", "x", "-k", "0"]) == 2


def test_cli_no_dream_subcommand():
    """Phase 0 freeze §3.1: the dream workflow is removed in v0.3.0. Calling
    `mneme dream <bundle>` must surface argparse's 'invalid choice' usage
    error (exit code 2). A passing test here means dream is NOT registered.
    """
    assert mneme.main(["dream", "wiki"]) == 2


def test_cli_lint_fails_with_clear_message_when_orphans_unimplemented(tmp_path, capsys):
    """Phase 0 freeze §3.3: `mneme lint` must (a) exist as a registered
    subcommand AND (b) report a deterministic message when the find_orphans
    primitive is not implemented yet. A plain argparse 'invalid choice'
    error (exit code 2) is not sufficient — it just means we forgot to wire
    the subcommand.
    """
    bundle = tmp_path / "wiki"
    bundle.mkdir()
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Test\n')
    (bundle / "concepts").mkdir()
    (bundle / "concepts" / "a.md").write_text(
        '---\ntype: Concept\ntitle: A\n---\n\nbody\n'
    )
    rc = mneme.main(["lint", str(bundle)])
    captured = capsys.readouterr()
    assert rc != 0
    assert rc != 2, (
        "argparse rejected 'lint' as 'invalid choice' — subcommand is not "
        "registered. PR1 must register the lint handler first."
    )
    assert "find_orphans not yet implemented" in captured.err, (
        f"lint handler ran but did not emit the unimplemented guard. "
        f"stderr was: {captured.err!r}"
    )
