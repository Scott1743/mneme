from pathlib import Path
import mneme


def test_init_scaffolds_bundle_and_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "mywiki"
    rc = mneme.main(["init", str(bundle), "--config", str(cfg)])
    assert rc == 0
    assert (bundle / "index.md").exists()
    assert (bundle / "log.md").exists()
    assert (bundle / "sources").is_dir()
    assert "okf_version" in (bundle / "index.md").read_text()
    assert f'bundle_path = "{bundle}"' in cfg.read_text()


def test_reindex_uses_injected_embed(tmp_path, monkeypatch):
    sample = Path(__file__).parent.parent / "sample-bundle"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'bundle_path = "{sample}"\n')
    import indexlib
    from test_indexlib import fake_embed
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: (lambda ts: fake_embed(ts, 8)))
    rc = mneme.main(["reindex", "--config", str(cfg)])
    assert rc == 0
    assert (sample / ".mneme" / "index.db").exists()
