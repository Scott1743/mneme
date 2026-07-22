from pathlib import Path
from mneme.tools_helpers import resolve_bundle, slug_from_path
import pytest
pytestmark = pytest.mark.unit


def test_resolve_bundle_from_config(tmp_path):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text('bundle_path = "/tmp/mywiki"\n')
    assert resolve_bundle(config_dir=config_dir, env={}, cwd=tmp_path) == Path("/tmp/mywiki")


def test_resolve_bundle_from_explicit_config_filename(tmp_path):
    config_path = tmp_path / "custom-mneme.toml"
    config_path.write_text('bundle_path = "/tmp/custom-wiki"\n')
    assert resolve_bundle(
        config_path=config_path, env={}, cwd=tmp_path
    ) == Path("/tmp/custom-wiki")


def test_resolve_bundle_env_fallback(tmp_path, monkeypatch):
    config_dir = tmp_path / "none"
    config_dir.mkdir()
    monkeypatch.setenv("MNEME_BUNDLE", "/env/wiki")
    assert resolve_bundle(config_dir=config_dir, env={"MNEME_BUNDLE": "/env/wiki"}, cwd=tmp_path) == Path("/env/wiki")


def test_slug_from_path():
    assert slug_from_path("My Note.md") == "my-note"
    assert slug_from_path("/a/b/Cool Paper.pdf") == "cool-paper"
