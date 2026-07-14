"""TOML config round-trip and edge cases (§2.4 + §5.4)."""
from pathlib import Path

import pytest
pytestmark = pytest.mark.unit

from mneme.config import ConfigError, read_config, retrieval_mode, set_retrieval_mode, write_config


def test_roundtrip_simple(tmp_path):
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/tmp/mywiki"})
    assert read_config(cfg) == {"bundle_path": "/tmp/mywiki"}


def test_roundtrip_path_with_space(tmp_path):
    """§5.4: bundle_path containing a space round-trips byte-for-byte."""
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/tmp/has space/wiki"})
    assert read_config(cfg) == {"bundle_path": "/tmp/has space/wiki"}


def test_roundtrip_path_with_embedded_double_quote(tmp_path):
    """§5.4: embedded double-quote is properly escaped on write and
    recovered on read."""
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": '/tmp/has"quote/wiki'})
    assert read_config(cfg) == {"bundle_path": '/tmp/has"quote/wiki'}


def test_roundtrip_path_with_backslash(tmp_path):
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/tmp/has\\backslash/wiki"})
    assert read_config(cfg) == {"bundle_path": "/tmp/has\\backslash/wiki"}


def test_roundtrip_chinese_path(tmp_path):
    """§5.4: non-ASCII path round-trips."""
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/tmp/笔记/wiki"})
    assert read_config(cfg) == {"bundle_path": "/tmp/笔记/wiki"}


def test_roundtrip_multiple_keys(tmp_path):
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/x", "model": "BAAI/bge", "k": 10})
    assert read_config(cfg) == {"bundle_path": "/x", "model": "BAAI/bge", "k": 10}


def test_read_empty_file_returns_empty_dict(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("", encoding="utf-8")
    assert read_config(cfg) == {}


def test_read_whitespace_only_file_returns_empty_dict(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("\n\n", encoding="utf-8")
    assert read_config(cfg) == {}


def test_write_then_read_byte_matches_original_intent(tmp_path):
    """A user-supplied path that contains every troublesome character
    we care about round-trips."""
    cfg = tmp_path / "config.toml"
    # Mix: space, quote, backslash, non-ASCII, plus a sane inner path.
    weird = '/tmp/mixed "quoted" \\b/笔记/wiki'
    write_config(cfg, {"bundle_path": weird})
    assert read_config(cfg) == {"bundle_path": weird}


def test_retrieval_mode_defaults_to_fts5_for_existing_configs(tmp_path):
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"bundle_path": "/tmp/wiki", "unknown_key": "kept"})

    assert retrieval_mode(cfg) == "fts5"
    set_retrieval_mode(cfg, "l2")
    assert read_config(cfg) == {
        "bundle_path": "/tmp/wiki",
        "unknown_key": "kept",
        "active_retrieval_mode": "l2",
    }


def test_retrieval_mode_rejects_invalid_config_value(tmp_path):
    cfg = tmp_path / "config.toml"
    write_config(cfg, {"active_retrieval_mode": "hybrid"})

    with pytest.raises(ConfigError, match="active_retrieval_mode"):
        retrieval_mode(cfg)
