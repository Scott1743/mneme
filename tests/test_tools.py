from pathlib import Path
from tools import resolve_bundle, slug_from_path


def test_resolve_bundle_from_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('bundle_path = "/tmp/mywiki"\n')
    assert resolve_bundle(config_path=cfg) == Path("/tmp/mywiki")


def test_resolve_bundle_env_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.setenv("MNEME_BUNDLE", "/env/wiki")
    assert resolve_bundle(config_path=cfg) == Path("/env/wiki")


def test_resolve_bundle_autodiscover_root_index(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.delenv("MNEME_BUNDLE", raising=False)
    bundle = tmp_path / "awiki"
    (bundle / "concepts").mkdir(parents=True)
    (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n# Concepts\n')
    monkeypatch.chdir(bundle / "concepts")
    assert resolve_bundle(config_path=cfg) == bundle


def test_slug_from_path():
    assert slug_from_path("My Note.md") == "my-note"
    assert slug_from_path("/a/b/Cool Paper.pdf") == "cool-paper"
