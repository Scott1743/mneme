"""Hand-rolled TOML writer — escape & type coverage.

These are the §4.1 red tests from
docs/superpowers/plans/2026-07-13-mneme-1.1.0-implementation.md.
Each test pins one escape or type-conversion edge case so a regression
in the writer doesn't silently corrupt ``~/.config/mneme/config.toml``.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
pytestmark = pytest.mark.unit


# tomllib is stdlib on 3.11+; tomli is the 3.10 fallback. Pick whichever
# is available so the round-trip tests work on both.
if sys.version_info >= (3, 11):
    import tomllib as _toml_read
else:  # pragma: no cover — Python 3.10 fallback
    try:
        import tomli as _toml_read  # type: ignore[import-nottyped]
    except ImportError:  # pragma: no cover
        _toml_read = None  # type: ignore[assignment]


pytestmark = pytest.mark.unit


def _read(path: Path) -> dict:
    """Helper: parse the writer's output back through stdlib TOML."""
    if _toml_read is None:
        pytest.skip("no TOML reader available (need Python 3.11+ or `tomli`)")
    text = path.read_text(encoding="utf-8")
    return _toml_read.loads(text) if text.strip() else {}


# ---------------------------------------------------------------------------
# §4.1 — escape edge cases
# ---------------------------------------------------------------------------

def test_toml_writer_basic_string(tmp_path):
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    write_config(target, {"bundle_path": "/foo/bar"})
    assert _read(target) == {"bundle_path": "/foo/bar"}


def test_toml_writer_escapes_double_quote(tmp_path):
    """Bundle path containing `"` must round-trip without truncation."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    weird = '/tmp/has"quote/wiki'
    write_config(target, {"bundle_path": weird})
    # Verify the file actually contains an escaped quote (not the raw char
    # which would terminate the string literal).
    text = target.read_text(encoding="utf-8")
    assert '\\"' in text, f"expected escaped quote in {text!r}"
    assert _read(target) == {"bundle_path": weird}


def test_toml_writer_escapes_backslash(tmp_path):
    """Windows-style backslashes must round-trip."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    weird = r"C:\Users\foo\wiki"
    write_config(target, {"bundle_path": weird})
    text = target.read_text(encoding="utf-8")
    assert "\\\\" in text, f"expected escaped backslash in {text!r}"
    assert _read(target) == {"bundle_path": weird}


def test_toml_writer_handles_unicode(tmp_path):
    """Non-ASCII codepoints pass through verbatim."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    weird = "/tmp/笔记/wiki"
    write_config(target, {"bundle_path": weird})
    assert _read(target) == {"bundle_path": weird}


def test_toml_writer_handles_newline_in_value(tmp_path):
    """Newlines are escaped to `\\n` rather than embedded raw (which
    would split the TOML line in half and break the parser)."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    weird = "/tmp/foo\nbar/wiki"
    write_config(target, {"bundle_path": weird})
    text = target.read_text(encoding="utf-8")
    assert "\\n" in text, f"expected escaped newline in {text!r}"
    # The file should still be exactly one logical line.
    assert text.count("\n") == 1, f"file has more than one line: {text!r}"
    assert _read(target) == {"bundle_path": weird}


def test_toml_writer_handles_tab_in_value(tmp_path):
    """Tabs are escaped to `\\t` for readability."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    weird = "/tmp/foo\tbar/wiki"
    write_config(target, {"bundle_path": weird})
    text = target.read_text(encoding="utf-8")
    assert "\\t" in text, f"expected escaped tab in {text!r}"
    assert _read(target) == {"bundle_path": weird}


def test_toml_writer_handles_int_and_bool(tmp_path):
    """int / bool / string round-trip with type preservation."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    write_config(target, {"k": 1, "v": True, "s": "x", "f": False})
    parsed = _read(target)
    assert parsed == {"k": 1, "v": True, "s": "x", "f": False}
    assert isinstance(parsed["v"], bool)
    assert isinstance(parsed["k"], int)


def test_toml_writer_handles_list_of_strings(tmp_path):
    """list[str] emits as TOML array; quote-bearing items are per-item escaped."""
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    write_config(target, {"k": ["a", 'b"c', "d"]})
    parsed = _read(target)
    assert parsed == {"k": ["a", 'b"c', "d"]}


def test_toml_writer_rejects_unsupported_types(tmp_path):
    """datetime / Path / arbitrary objects raise TypeError loudly."""
    import datetime
    from pathlib import Path as _P
    from mneme.toml_writer import write_config
    target = tmp_path / "cfg.toml"
    with pytest.raises(TypeError, match="does not support"):
        write_config(target, {"k": datetime.datetime(2026, 7, 13)})
    with pytest.raises(TypeError, match="does not support"):
        write_config(target, {"k": _P("/tmp/foo")})