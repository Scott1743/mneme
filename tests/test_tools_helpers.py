from pathlib import Path
from mneme.tools_helpers import resolve_bundle, slug_from_path


def test_resolve_bundle_from_config(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text('bundle_path = "/tmp/mywiki"\n')
    assert resolve_bundle(config_path=cfg) == Path("/tmp/mywiki")


def test_resolve_bundle_env_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "none.toml"
    monkeypatch.setenv("MNEME_BUNDLE", "/env/wiki")
    assert resolve_bundle(config_path=cfg) == Path("/env/wiki")


def test_slug_from_path():
    assert slug_from_path("My Note.md") == "my-note"
    assert slug_from_path("/a/b/Cool Paper.pdf") == "cool-paper"
