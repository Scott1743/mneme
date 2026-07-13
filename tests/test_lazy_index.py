"""L2 lazy install — §5 / §5.3-bis / §5.3-ter red tests.

These pin v1.1.0's central user-experience claim: a skill.sh user who
runs ``mneme search`` or ``mneme reindex`` for the first time gets L2
deps installed transparently (with PEP 668 awareness), instead of a raw
``ModuleNotFoundError: No module named 'sqlite_vec'``.

Each test mocks subprocess / os.execvp so the real ``pip install`` and
``os.execvp`` never fire — we observe the call shape instead.
"""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock
import pytest
pytestmark = pytest.mark.unit


def _install_spy(monkeypatch):
    """Replace ``subprocess.check_call`` with a recording spy."""
    calls = []
    monkeypatch.setattr(
        "subprocess.check_call",
        lambda *a, **kw: calls.append(a[0]) or 0,
    )
    return calls


def _execvp_spy(monkeypatch):
    """Replace ``os.execvp`` with a recording spy that aborts the test.

    os.execvp never returns; if it did, the Python process would be
    replaced and the test runner itself would die. The spy records
    the args then raises ``RuntimeError`` so the test gets a clean
    observable exception.
    """
    calls = []

    def fake(file, args):
        calls.append((file, list(args)))
        raise RuntimeError(f"execvp: {file} {args}")

    monkeypatch.setattr("os.execvp", fake)
    return calls


def _drop_lazy_index_cache():
    """Make sure each test gets a fresh import of lazy_index.ensure_index_deps.

    The previous test may have cached sys.modules['sqlite_vec'] = ...;
    dropping the lazy_index module too avoids any stale state.
    """
    sys.modules.pop("mneme.lazy_index", None)


def _block_sqlite_vec(monkeypatch):
    """Force ``import sqlite_vec`` to fail.

    Sets ``sys.modules['sqlite_vec'] = None`` — Python's import machinery
    treats a None entry as "module is known to be unimportable" and
    raises ``ImportError`` without trying to actually import it. This
    is more reliable than ``delitem`` (which lets Python attempt a
    fresh import and may succeed if the dep is installed in the venv).
    """
    monkeypatch.setitem(sys.modules, "sqlite_vec", None)


# ---------------------------------------------------------------------------
# §5.1 — import detection
# ---------------------------------------------------------------------------

def test_lazy_index_noop_when_already_installed(monkeypatch):
    """If ``sqlite_vec`` is already importable, ``ensure_index_deps``
    returns immediately and does NOT touch pip or execvp."""
    monkeypatch.setitem(sys.modules, "sqlite_vec", MagicMock())
    install_calls = _install_spy(monkeypatch)
    execvp_calls = _execvp_spy(monkeypatch)
    _drop_lazy_index_cache()

    from mneme.lazy_index import ensure_index_deps
    ensure_index_deps()
    assert install_calls == []
    assert execvp_calls == []


def test_lazy_index_detects_missing_sqlite_vec(monkeypatch):
    """When ``sqlite_vec`` is missing, ``ensure_index_deps`` invokes
    pip install with the right argv shape."""
    _block_sqlite_vec(monkeypatch)
    install_calls = _install_spy(monkeypatch)
    execvp_calls = _execvp_spy(monkeypatch)
    _drop_lazy_index_cache()

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(RuntimeError, match="execvp"):
        ensure_index_deps()

    assert len(install_calls) == 1
    cmd = install_calls[0]
    assert "-m" in cmd and "pip" in cmd and "install" in cmd
    assert cmd[-1] == "mneme[index]"
    # And the install was followed by an execvp.
    assert len(execvp_calls) == 1


# ---------------------------------------------------------------------------
# §5.3 — offline / permission graceful failure
# ---------------------------------------------------------------------------

def test_lazy_install_offline_returns_clear_error(monkeypatch, capsys):
    """``subprocess.check_call`` failure → ``SystemExit`` with manual
    install hint in stderr. Never a raw stack trace."""
    _block_sqlite_vec(monkeypatch)
    _drop_lazy_index_cache()

    def fake_check_call(*a, **kw):
        raise subprocess.CalledProcessError(
            returncode=1, cmd=a[0], output="", stderr="network unreachable",
        )

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(SystemExit) as exc_info:
        ensure_index_deps()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "pip install" in captured.err
    assert "mneme[index]" in captured.err
    # No raw traceback leaked to stderr.
    assert "Traceback" not in captured.err


def test_lazy_install_permission_denied_returns_clear_error(monkeypatch, capsys):
    """PermissionError → SystemExit with venv / --user guidance."""
    _block_sqlite_vec(monkeypatch)
    _drop_lazy_index_cache()

    def fake_check_call(*a, **kw):
        raise PermissionError(13, "operation not permitted", "/usr/lib/python3.13/site-packages")

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(SystemExit) as exc_info:
        ensure_index_deps()
    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Permission denied" in captured.err or "permission" in captured.err.lower()
    # Should suggest either venv or --user
    assert "venv" in captured.err or "--user" in captured.err


# ---------------------------------------------------------------------------
# §5.3-bis — PEP 668 awareness
# ---------------------------------------------------------------------------

def test_lazy_install_uses_user_flag_on_system_python(monkeypatch):
    """When ``sys.prefix == sys.base_prefix`` (system Python), the pip
    argv includes ``--user`` to dodge PEP 668 externally-managed errors."""
    _block_sqlite_vec(monkeypatch)
    # Pretend we're on system Python, not in a venv.
    monkeypatch.setattr(sys, "prefix", "/usr")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    install_calls = _install_spy(monkeypatch)
    _execvp_spy(monkeypatch)  # aborts cleanly after install
    _drop_lazy_index_cache()

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(RuntimeError, match="execvp"):
        ensure_index_deps()

    cmd = install_calls[0]
    assert "--user" in cmd, f"system Python should pass --user to pip; got {cmd!r}"
    assert cmd[-1] == "mneme[index]"


def test_lazy_install_skips_user_flag_in_venv(monkeypatch):
    """When ``sys.prefix != sys.base_prefix`` (venv), the pip argv
    does NOT include ``--user`` (the venv is its own site-packages)."""
    _block_sqlite_vec(monkeypatch)
    # Pretend we're inside a venv.
    monkeypatch.setattr(sys, "prefix", "/home/user/.venvs/mneme")
    monkeypatch.setattr(sys, "base_prefix", "/usr")
    install_calls = _install_spy(monkeypatch)
    _execvp_spy(monkeypatch)
    _drop_lazy_index_cache()

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(RuntimeError, match="execvp"):
        ensure_index_deps()

    cmd = install_calls[0]
    assert "--user" not in cmd, f"venv install should not use --user; got {cmd!r}"
    assert cmd[-1] == "mneme[index]"


# ---------------------------------------------------------------------------
# §5.3-ter — re-exec self after install
# ---------------------------------------------------------------------------

def test_lazy_install_reexecs_self_after_install(monkeypatch):
    """After a successful install, ``os.execvp`` is called with the
    current ``sys.executable`` + ``-m mneme`` + the user's original
    ``sys.argv[1:]``. So the freshly-installed deps are loaded into a
    fresh interpreter and the user's command runs to completion."""
    _block_sqlite_vec(monkeypatch)
    _install_spy(monkeypatch)
    execvp_calls = _execvp_spy(monkeypatch)
    monkeypatch.setattr(
        sys, "argv",
        ["mneme.py", "reindex", "--config", "/tmp/cfg.toml"],
    )
    _drop_lazy_index_cache()

    from mneme.lazy_index import ensure_index_deps
    with pytest.raises(RuntimeError, match="execvp"):
        ensure_index_deps()

    assert len(execvp_calls) == 1
    file, args = execvp_calls[0]
    assert file == sys.executable
    assert args[0] == sys.executable
    assert args[1] == "-m"
    assert args[2] == "mneme"
    # The user's original argv (excluding the script name) is preserved.
    assert args[3:] == ["reindex", "--config", "/tmp/cfg.toml"]