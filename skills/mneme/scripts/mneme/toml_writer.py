"""Hand-rolled TOML writer for mneme's limited config schema.

Replaces ``tomli_w`` with ~60 lines of stdlib-only code. Supports only
the types mneme actually writes to ``~/.config/mneme/config.toml``:

- ``str`` — quoted with backslash + double-quote escaping
- ``int``, ``float``, ``bool`` — literal forms
- ``list`` of scalars — TOML arrays

Anything else raises ``TypeError``. The reader (``tomllib`` / ``tomli``)
will reject malformed TOML on its end if a bug ever slips through.

The output is one key per line, no section headers — mneme's config
is a single flat namespace (``bundle_path = "..."`` and friends). A
round-trip through ``read_config`` yields the same dict.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


def _escape_str(value: str) -> str:
    """Escape a string for inclusion in a TOML basic string literal.

    TOML basic strings are double-quoted. We escape the three always-unsafe
    chars (``\\``, ``"``, newline) plus ``\\r`` / ``\\t`` for readability.
    Other ASCII control characters (0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F)
    are emitted as ``\\uXXXX`` so the output stays parser-clean. Non-ASCII
    codepoints pass through verbatim (TOML allows raw unicode).
    """
    out = []
    for ch in value:
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif cp < 0x20 or cp == 0x7F:
            out.append(f"\\u{cp:04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _emit(value: Any) -> str:
    """Render one TOML scalar or array.

    Raises ``TypeError`` on unsupported types — better to fail loudly
    than to silently emit invalid TOML.
    """
    # bool must be checked before int (bool is a subclass of int in Python).
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _escape_str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_emit(v) for v in value) + "]"
    raise TypeError(
        f"toml_writer does not support {type(value).__name__!r}; "
        "supported types: str, int, float, bool, list"
    )


def write_config(path: Path, data: Mapping[str, Any]) -> None:
    """Write a flat dict as TOML.

    Output format::

        key1 = <scalar>
        key2 = <scalar>
        ...

    Empty data produces an empty file (which ``read_config`` parses as
    ``{}``). Keys must be non-empty strings; values must be one of the
    supported scalar types or a list thereof.
    """
    lines = []
    for key, value in data.items():
        if not isinstance(key, str) or not key:
            raise ValueError(
                f"config keys must be non-empty strings; got {key!r}"
            )
        lines.append(f"{key} = {_emit(value)}\n")
    Path(path).write_text("".join(lines), encoding="utf-8")