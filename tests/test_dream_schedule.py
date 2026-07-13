"""`mneme dream --schedule` / `--unschedule` helper contract.

The helper prints a platform-specific scheduler snippet:

  * macOS (``sys.platform == "darwin"``)  -> launchd plist XML
  * Linux / other unix-likes              -> crontab line
  * Windows (``win32``)                   -> ``schtasks /Create`` line

It is **print-only**: it never invokes ``launchctl``, never touches the
user's crontab, never runs ``schtasks``. The user inspects the snippet and
pastes / saves it themselves. ``mneme dream`` stays read-only by design
(frozen contract enforced by ``tests/test_dream_readonly.py``); this
helper just hands the user a snippet instead of a live install.

The four tests below lock in:

  1. The macOS path emits ``LaunchAgents`` + ``plist`` + the bundle path
     + the default 02:00 schedule.
  2. The Linux path emits a ``cron``-shaped line with the user's
     ``--time`` value and the bundle path.
  3. The Windows path emits a ``schtasks`` line with the user's
     ``--time`` value and the bundle path.
  4. Neither flag shells out via ``subprocess.run`` (no surprise
     ``launchctl`` / ``crontab`` / ``schtasks`` invocation).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
pytestmark = pytest.mark.unit


def _bundle(tmp_path: Path, name: str = "wiki") -> Path:
    b = tmp_path / name
    b.mkdir()
    (b / "index.md").write_text("---\nokf_version: \"0.1\"\n---\n\n# Index\n")
    return b


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def test_dream_schedule_macos_emits_launchd_plist_with_default_time(
    tmp_path, monkeypatch, capsys
) -> None:
    from mneme import cli

    bundle = _bundle(tmp_path, name="notebooks")
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    rc = cli.main(["dream", "--bundle", str(bundle), "--schedule"])
    out = capsys.readouterr().out

    assert rc == 0, f"dream --schedule must exit 0 on macOS; rc={rc}"
    # Platform signature
    assert "LaunchAgents" in out, (
        f"macOS schedule snippet missing 'LaunchAgents'; out={out!r}"
    )
    assert "plist" in out.lower(), (
        f"macOS schedule snippet missing plist markup; out={out!r}"
    )
    # Bundle path must appear verbatim so the user can audit the snippet
    # before saving it into ~/Library/LaunchAgents/...
    assert str(bundle) in out, (
        f"macOS schedule snippet missing the bundle path {bundle}; "
        f"out={out!r}"
    )
    # Default 02:00 -- startCalendarInterval hour=2, minute=0
    assert "<integer>2</integer>" in out, (
        f"default hour (2 = 02:00) missing from macOS plist; out={out!r}"
    )
    assert "<integer>0</integer>" in out, (
        f"default minute (0 = :00) missing from macOS plist; out={out!r}"
    )


# ---------------------------------------------------------------------------
# Linux / unix-likes
# ---------------------------------------------------------------------------


def test_dream_schedule_linux_emits_crontab_with_custom_time(
    tmp_path, monkeypatch, capsys
) -> None:
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", "linux")

    rc = cli.main(
        [
            "dream",
            "--bundle",
            str(bundle),
            "--schedule",
            "--time",
            "03:30",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 0, f"dream --schedule must exit 0 on Linux; rc={rc}"
    # crontab shape: `M H * * * ...` -- 30 3 * * *
    assert "30 3 * * *" in out, (
        f"linux crontab snippet missing '30 3 * * *'; out={out!r}"
    )
    # Platform / vocabulary keyword
    assert "crontab" in out.lower() or "cron" in out.lower(), (
        f"linux snippet missing 'cron' vocabulary; out={out!r}"
    )
    # Bundle path present so the user can audit before pasting
    assert str(bundle) in out, (
        f"linux crontab snippet missing bundle path {bundle}; out={out!r}"
    )
    # The dispatch target is the python interpreter
    assert "mneme" in out and "dream" in out, (
        f"linux crontab snippet missing 'mneme dream --bundle ...'; out={out!r}"
    )


def test_dream_unschedule_darwin_emits_launchctl_unload(
    tmp_path, monkeypatch, capsys
) -> None:
    """`--unschedule` mirrors `--schedule` with the platform's removal
    verb (launchctl unload / rm on macOS)."""
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", "darwin")

    rc = cli.main(["dream", "--bundle", str(bundle), "--unschedule"])
    out = capsys.readouterr().out

    assert rc == 0, f"dream --unschedule must exit 0; rc={rc}"
    assert "launchctl" in out, (
        f"macOS unschedule snippet missing 'launchctl'; out={out!r}"
    )
    # Removal verb (launchctl unload OR rm .plist) and the plist path
    assert "unload" in out or "rm " in out, (
        f"macOS unschedule snippet missing unload/rm verb; out={out!r}"
    )
    assert "plist" in out.lower(), (
        f"macOS unschedule snippet missing plist reference; out={out!r}"
    )


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def test_dream_schedule_windows_emits_schtasks_with_time(
    tmp_path, monkeypatch, capsys
) -> None:
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", "win32")

    rc = cli.main(
        [
            "dream",
            "--bundle",
            str(bundle),
            "--schedule",
            "--time",
            "04:15",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 0, f"dream --schedule must exit 0 on Windows; rc={rc}"
    # Platform signature
    assert "schtasks" in out, (
        f"windows schedule snippet missing 'schtasks'; out={out!r}"
    )
    # Schedule time honoured
    assert "04:15" in out, (
        f"windows schedule snippet missing --time 04:15; out={out!r}"
    )
    # Bundle path present so the user can audit
    assert str(bundle) in out, (
        f"windows schedule snippet missing bundle path {bundle}; out={out!r}"
    )


# ---------------------------------------------------------------------------
# Safety: --schedule / --unschedule must not shell out.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_dream_schedule_does_not_shell_out(
    tmp_path, monkeypatch, capsys, platform
) -> None:
    """Neither flag may invoke ``subprocess.run``. The helper is
    print-only — the user installs the snippet themselves."""
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", platform)

    calls: list = []
    real_run = subprocess.run

    def spy(args, *a, **kw):
        calls.append((str(args), a, kw))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", spy)

    rc = cli.main(["dream", "--bundle", str(bundle), "--schedule"])
    rc_un = cli.main(["dream", "--bundle", str(bundle), "--unschedule"])

    # Restore real run so the test process isn't accidentally disturbed.
    monkeypatch.setattr(subprocess, "run", real_run)

    assert rc == 0 and rc_un == 0, (
        f"--schedule/--unschedule must exit 0; got rc={rc}, rc_un={rc_un}"
    )
    assert calls == [], (
        f"`mneme dream --schedule/--unschedule` shelled out via "
        f"subprocess.run; calls={calls!r}"
    )


# ---------------------------------------------------------------------------
# Flag conflicts and input validation
# ---------------------------------------------------------------------------


def test_dream_schedule_and_unschedule_together_returns_usage_error(
    tmp_path, monkeypatch, capsys
) -> None:
    """Passing both flags is a usage error (exit 2)."""
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", "linux")

    rc = cli.main(
        ["dream", "--bundle", str(bundle), "--schedule", "--unschedule"]
    )
    captured = capsys.readouterr()

    assert rc == 2, (
        f"--schedule + --unschedule must exit 2 (usage error); got rc={rc}"
    )
    assert "mutually exclusive" in captured.err.lower(), (
        f"expected 'mutually exclusive' on stderr; err={captured.err!r}"
    )


def test_dream_schedule_invalid_time_returns_usage_error(
    tmp_path, monkeypatch, capsys
) -> None:
    """``--time 25:00`` is out of range and must exit 2 with a clear error."""
    from mneme import cli

    bundle = _bundle(tmp_path)
    monkeypatch.setattr(cli.sys, "platform", "linux")

    rc = cli.main(
        ["dream", "--bundle", str(bundle), "--schedule", "--time", "25:00"]
    )
    captured = capsys.readouterr()

    assert rc == 2, f"invalid --time must exit 2; got rc={rc}"
    assert "out of range" in captured.err.lower() or "25:00" in captured.err, (
        f"expected 'out of range' or echoed value on stderr; err={captured.err!r}"
    )
