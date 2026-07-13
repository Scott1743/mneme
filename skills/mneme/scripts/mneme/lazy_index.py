"""L2 (sqlite-vec + fastembed) lazy install for v1.1.0.

When the user runs ``mneme reindex`` or ``mneme search`` for the first
time, the OKF core needs L2 deps. Rather than make the user run a
separate ``pip install 'mneme[index]'`` step, we install on demand:

- **In a venv:** ``pip install mneme[index]`` (the venv is isolated)
- **On system Python:** ``pip install --user mneme[index]`` to avoid
  PEP 668 externally-managed-environment errors (macOS 14+, modern
  PEP 668 distros)

After successful install, the current Python process does not see the
new packages yet (imports are cached for the lifetime of a process). We
re-exec the CLI via ``os.execvp`` so the freshly-installed deps are
loaded and the user's original command runs to completion.

If the install fails for any reason (offline, permission denied, no
``pip`` at all), we exit with a clear ``SystemExit`` pointing the user
at the manual command — never a raw stack trace.
"""
from __future__ import annotations

import os
import subprocess
import sys


def _in_venv() -> bool:
    """True when running inside a virtualenv or similar isolated env.

    Uses the standard ``sys.prefix != sys.base_prefix`` test. PEP 668
    does NOT consider a venv externally-managed, so venv installs use
    plain ``pip install`` (no ``--user``).
    """
    base = getattr(sys, "base_prefix", sys.prefix)
    return sys.prefix != base


def _pip_install_cmd() -> list[str]:
    """Build the pip install argv for the ``[index]`` extras.

    Honors PEP 668 by adding ``--user`` on system Python installs.
    Venv installs stay clean (no ``--user``) since the venv is its own
    writable site-packages.
    """
    cmd = [sys.executable, "-m", "pip", "install"]
    if not _in_venv():
        cmd.append("--user")
    cmd.append("mneme[index]")
    return cmd


def ensure_index_deps() -> None:
    """Make sure ``sqlite_vec`` is importable; install on demand.

    Behavior on each call:

    1. ``import sqlite_vec`` — if it succeeds, return immediately.
    2. Otherwise, print a one-time notice and run ``pip install
       mneme[index]`` with PEP 668-aware flags.
    3. On install success: re-exec the current process via
       ``os.execvp`` with the original ``sys.argv`` so the new
       packages are loaded and the user's command completes.
    4. On install failure: ``SystemExit`` with a clear manual-install
       instruction. Never raises the raw subprocess / OSError.

    The ``os.execvp`` on success replaces the current process; no
    Python code after the call ever runs in the original interpreter.
    """
    try:
        import sqlite_vec  # noqa: F401
        return  # already installed — fast path
    except ImportError:
        pass

    cmd = _pip_install_cmd()
    pretty = " ".join(cmd)
    print(
        "\nFirst-time L2 use: installing semantic search dependencies\n"
        f"  $ {pretty}\n"
        "  (one-time; includes a ~90MB embedding model download)\n",
        file=sys.stderr,
    )

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(
            f"\nFailed to install semantic search dependencies: {exc}\n"
            "Install manually with: pip install 'mneme[index]'\n"
        )
        raise SystemExit(1) from exc
    except (PermissionError, OSError) as exc:
        # macOS 14+ and many Linux distros block system pip installs
        # (PEP 668). --user usually works but may also fail on locked
        # down systems. Give the user a clear path forward.
        sys.stderr.write(
            f"\nFailed to install semantic search dependencies: {exc}\n"
            "Permission denied. Try one of:\n"
            "  - Use a virtualenv: python3 -m venv .venv && source .venv/bin/activate\n"
            "  - Install with --user: pip install --user 'mneme[index]'\n"
            "  - Install via your system package manager\n"
        )
        raise SystemExit(1) from exc

    # Re-exec self with the original argv so the freshly-installed deps
    # are visible to the new Python process. ``-m mneme`` works as long
    # as cwd contains the ``mneme/`` package (skill.sh users cd into
    # ``~/.claude/skills/mneme/scripts/``); tests inherit PYTHONPATH
    # from conftest.py.
    new_argv = [sys.executable, "-m", "mneme", *sys.argv[1:]]
    os.execvp(sys.executable, new_argv)