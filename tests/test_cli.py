import json
from pathlib import Path

import indexlib
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
