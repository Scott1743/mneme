#!/usr/bin/env python3
"""Thin mneme CLI for bundle setup and deterministic L2 operations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

def _default_config_path() -> Path:
    from .config import resolve_config_dir

    return resolve_config_dir() / "config.toml"


def _limit(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return parsed


def _query(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty")
    return value


def _write_config(bundle_path: Path, config_path: Path) -> None:
    from .config import write_config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    write_config(config_path, {"bundle_path": str(bundle_path)})


def _resolve_bundle(args: argparse.Namespace) -> Path | None:
    explicit = getattr(args, "bundle", None)
    if explicit:
        bundle = Path(explicit)
        return bundle if bundle.is_dir() else None

    from .tools_helpers import resolve_bundle

    config_path = getattr(args, "config", None)
    if not config_path:
        config_path = _default_config_path()
    config_dir = Path(config_path).parent
    return resolve_bundle(config_dir=config_dir, env=None, cwd=Path.cwd())


def cmd_init(args: argparse.Namespace) -> int:
    bundle = Path(args.path)
    config = Path(args.config)
    if bundle.exists():
        print(f"bundle already exists: {bundle}", file=sys.stderr)
        return 1
    bundle.mkdir(parents=True)
    (bundle / "sources").mkdir(exist_ok=True)
    (bundle / "sources" / ".gitkeep").touch(exist_ok=True)
    if not (bundle / "index.md").exists():
        (bundle / "index.md").write_text(
            '---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8"
        )
    if not (bundle / "log.md").exists():
        (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    _write_config(bundle, config)
    print(f"initialized bundle at {bundle}; recorded in {config}")
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """v2.1 reindex: rebuild the L1 (sqlite3 + FTS5) index by default;
    with ``--l2``, rebuild the L2 (sqlite-vec + FastEmbed) index.

    Default path walks ``*.md`` under the bundle (excluding ``.mneme/``,
    ``sources/``, and ``external-sources/``), parses each page's
    frontmatter, and writes one ``pages`` row + ``pages_fts`` insertion
    per page via Task 3's atomic snapshot rebuild.

    The ``--l2`` flag opts into the v1.x L2 path: ``indexlib.reindex_bundle``
    with the BAAI/bge-small-zh-v1.5 embedder. L2 deps
    (``sqlite-vec`` + ``fastembed``) are user-installed; we surface a
    one-line install hint instead of an ImportError traceback when they
    are missing.
    """
    bundle = _resolve_bundle(args)
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1
    from . import indexlib

    bundle = Path(bundle)
    if getattr(args, "l2", False):
        # v2.1: explicit opt-in L2 path. The legacy `reindex_bundle`
        # requires sqlite-vec + fastembed; surface a clean one-line
        # install hint if either is missing instead of an ImportError
        # traceback.
        try:
            embed_fn = indexlib.default_embed_fn()
        except indexlib.FastEmbedUnavailableError as exc:
            print(
                f"reindex --l2 failed: {exc}",
                file=sys.stderr,
            )
            return 1
        try:
            result = indexlib.reindex_bundle(bundle, embed_fn)
        except indexlib.SqliteVecUnavailableError as exc:
            print(
                f"reindex --l2 failed: {exc}",
                file=sys.stderr,
            )
            return 1
        except Exception as exc:
            print(f"reindex --l2 failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"indexed {result.indexed_concepts} concept(s) / "
            f"{result.indexed_chunks} chunk(s) into {result.db_path} "
            f"(L2: {embed_fn.model_name})"
        )
        return 0

    paths: list[Path] = []
    for p in sorted(bundle.rglob("*.md")):
        if not p.is_file():
            continue
        parts = p.relative_to(bundle).parts
        if any(part == ".mneme" for part in parts):
            continue
        if "sources" in parts:
            continue
        if "external-sources" in parts:
            continue
        paths.append(p)

    try:
        indexed = indexlib.reindex_paths(paths, bundle)
    except Exception as exc:
        print(f"reindex failed: {exc}", file=sys.stderr)
        return 1
    print(f"indexed {indexed} page(s) into {bundle / '.mneme' / 'index.db'}")
    return 0


# v2.0 search surface — see
# docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md Task 4.
# Search returns *candidates* (path + title + snippet) only; the host
# agent reads each candidate page in full to compose the final answer.
# Two paths:
#   1. FTS5 against <bundle>/.mneme/index.db (default; built by
#      `mneme reindex` via Task 3's reindex_paths).
#   2. L0 grep fallback over *.md when index.db is missing.
# No L2 deps (sqlite-vec + fastembed) are imported here; those land
# in v2.1.

_L0_GREP_CONTEXT = 60  # chars of context around the matched line


def _cmd_search_grep(bundle: Path, query: str, k: int) -> Dict:
    """L0 fallback: walk ``*.md`` files in the bundle, parse
    frontmatter for the title, and case-insensitively scan the body
    for ``query``. Returns the same ``{"query": ..., "candidates": [...]}``
    shape as :func:`indexlib.search` so the caller doesn't branch.
    """
    from . import okflib

    q = query.lower()
    candidates: List[Dict] = []
    for md_path in sorted(bundle.rglob("*.md")):
        if not md_path.is_file():
            continue
        parts = md_path.relative_to(bundle).parts
        if any(part == ".mneme" for part in parts):
            continue
        # Raw sources under sources/ are immutable inputs — they have
        # no frontmatter and shouldn't be surfaced as OKF concepts.
        if "sources" in parts:
            continue
        if md_path.name in ("index.md", "log.md"):
            continue
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        parsed = okflib.parse_frontmatter(text)
        title = ""
        body = text
        if parsed is not None:
            meta, body = parsed
            title = str(meta.get("title", "") or "")
        if q not in title.lower() and q not in body.lower():
            continue
        snippet = _make_grep_snippet(body, q, _L0_GREP_CONTEXT)
        rel = md_path.relative_to(bundle).as_posix()
        candidates.append({"path": rel, "title": title, "snippet": snippet})
        if len(candidates) >= k:
            break
    return {"query": query, "candidates": candidates}


def _make_grep_snippet(body: str, query_lower: str, context: int) -> str:
    """Build a short snippet around the first body match of ``query_lower``.

    Truncates to a single line so the agent's candidate list stays
    scannable; falls back to a head-of-body snippet when no match
    exists (which shouldn't happen because the caller already
    filtered on the match, but keeps the function defensive).
    """
    lines = body.splitlines()
    for line in lines:
        if query_lower in line.lower():
            stripped = line.strip()
            if len(stripped) <= context * 2:
                return stripped
            idx = stripped.lower().find(query_lower)
            start = max(0, idx - context)
            end = min(len(stripped), idx + len(query_lower) + context)
            return stripped[start:end]
    # Defensive fallback — body had the match per the caller, but no
    # single line did (e.g. match spans a line boundary). Trim head.
    head = " ".join(lines).strip()
    return head if len(head) <= context * 2 else f"{head[: context * 2]}..."


def cmd_search(args: argparse.Namespace) -> int:
    """v2.1 search: candidates + snippets via FTS5 by default; with
    ``--l2``, the legacy L2 (sqlite-vec + FastEmbed) path.

    The ``--l2`` path requires an L2-built index (i.e. ``mneme reindex
    --l2`` must have been run); if the index is FTS5-only, ``--l2``
    errors with a clear hint rather than silently falling back. FTS5
    is the default — ``--l2`` is explicit opt-in.
    """
    bundle = _resolve_bundle(args)
    if bundle is None:
        print(
            "no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init",
            file=sys.stderr,
        )
        return 1

    from . import indexlib

    db = bundle / ".mneme" / "index.db"

    if getattr(args, "l2", False):
        # v2.1: --l2 is explicit opt-in. It must NOT silently fall back
        # to FTS5 — that would be a foot-gun. Check that an L2-shaped
        # index exists (vec_chunks table is the L2 sentinel) and error
        # with a clear remediation if not.
        if not db.is_file():
            print(
                "no index at "
                f"{db}; --l2 requires an L2-built index. "
                "Run `mneme reindex --l2` first.",
                file=sys.stderr,
            )
            return 1
        try:
            import sqlite3 as _sqlite3
            with _sqlite3.connect(str(db)) as _conn:
                _has_vec = _conn.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name='vec_chunks'"
                ).fetchone()
        except Exception as exc:
            print(f"search --l2 failed: {exc}", file=sys.stderr)
            return 1
        if not _has_vec:
            print(
                f"index at {db} is FTS5-only (no vec_chunks table); "
                "--l2 requires an L2-built index. "
                "Run `mneme reindex --l2` first.",
                file=sys.stderr,
            )
            return 1
        try:
            hits = indexlib.search_bundle(
                bundle,
                args.query,
                k=args.limit,
                embed_fn=indexlib.default_embed_fn(),
            )
        except indexlib.FastEmbedUnavailableError as exc:
            print(
                f"search --l2 failed: {exc}",
                file=sys.stderr,
            )
            return 1
        except indexlib.SqliteVecUnavailableError as exc:
            print(
                f"search --l2 failed: {exc}",
                file=sys.stderr,
            )
            return 1
        except Exception as exc:
            print(f"search --l2 failed: {exc}", file=sys.stderr)
            return 1
        out = {
            "query": args.query,
            "candidates": [
                {
                    "path": h.get("path", ""),
                    "title": h.get("title", ""),
                    "snippet": h.get("text", ""),
                }
                for h in hits
            ],
        }
    elif db.is_file():
        try:
            out = indexlib.search(args.query, db, k=args.limit)
        except Exception as exc:
            print(f"search failed: {exc}", file=sys.stderr)
            return 1
    else:
        # L0 grep fallback. Don't write the index here — the user
        # opted out of `mneme reindex`. Just nudge on stderr.
        print(
            f"no index at {db}; falling back to L0 grep. "
            "Run `mneme reindex` for full-text ranking.",
            file=sys.stderr,
        )
        out = _cmd_search_grep(bundle, args.query, args.limit)

    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for candidate in out["candidates"]:
            # FTS5 snippet() may return multi-line fragments (e.g.
            # `# h\n|rareword| appears here\n`); collapse to a single
            # line so the tab-separated human output stays scannable.
            snippet = candidate["snippet"].replace("\n", " ").strip()
            print(
                f"{candidate['path']}\t{candidate['title']}\t{snippet}"
            )
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    """Validate one bundle; exit 1 only when OKF ERROR diagnostics exist.

    Pipeline (Task 5 — see
    docs/superpowers/plans/2026-07-13-mneme-2.0-implementation.md):
      1. :func:`okflib.lint_bundle` — wraps :func:`okflib.validate_bundle`
         and appends MNEME-TAG-MISSING for concept pages lacking
         ``tags``. The base OKF validator is *not* reimplemented; the
         wrapper only translates its ``Report`` into flat diagnostics.
      2. :func:`okflib.find_orphans` — orphan analysis (always printed).

    Exit codes (frozen by Pre-Task B):
      0 — no ERROR diagnostics (WARN-only bundles exit 0).
      1 — at least one ERROR diagnostic, OR the bundle could not be
          resolved.
    """
    explicit = getattr(args, "path", None)
    if explicit:
        args = argparse.Namespace(
            bundle=explicit,
            **{k: v for k, v in vars(args).items() if k not in {"path", "bundle"}},
        )
    bundle = _resolve_bundle(args)
    if bundle is None:
        print("no bundle found; set bundle_path, MNEME_BUNDLE, or run mneme init", file=sys.stderr)
        return 1

    from . import okflib

    report = okflib.lint_bundle(bundle, require_tags=True)
    diagnostics = report.get("diagnostics", [])

    errors_count = 0
    warnings_count = 0
    for d in diagnostics:
        # Same `{SEVERITY}  {path}: [{rule}] {detail}` shape as
        # `validate_okf.print_report` so existing log parsers
        # (test_e2e_lint._parse_report etc.) keep working.
        if d["severity"] == "ERROR":
            errors_count += 1
        else:
            warnings_count += 1
        print(f"{d['severity']}  {d['path']}: [{d['code']}] {d['detail']}")
    print(f"\n{errors_count} error(s), {warnings_count} warning(s)")

    orphans = okflib.find_orphans(bundle)
    print(f"\norphan concept pages ({len(orphans)}):", file=sys.stderr)
    for slug in orphans:
        print(f"  - {slug}", file=sys.stderr)
    return 1 if errors_count else 0


def cmd_dream(args: argparse.Namespace) -> int:
    """`mneme dream` — read-only audit; ``--schedule`` / ``--unschedule``
    print platform-specific scheduler snippets for the user to install.

    Without ``--schedule`` / ``--unschedule``, behaves as the read-only
    audit (Task 6 — ``dream_audit``). With either flag, prints a snippet
    and exits; never invokes ``launchctl``, ``crontab``, ``schtasks`` or
    any other side-effecting command. The user reviews the snippet and
    pastes / saves it themselves — ``mneme dream`` stays read-only by
    design (frozen contract enforced by ``tests/test_dream_readonly.py``).
    """
    schedule = getattr(args, "schedule", False)
    unschedule = getattr(args, "unschedule", False)
    if schedule and unschedule:
        print(
            "--schedule and --unschedule are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    if schedule or unschedule:
        bundle = _resolve_bundle(args)
        if bundle is None:
            print(
                "no bundle found; pass --bundle or set MNEME_BUNDLE / "
                "config.toml [bundle_path]",
                file=sys.stderr,
            )
            return 1
        hh, mm, err = _parse_dream_time(getattr(args, "time", None))
        if err is not None:
            print(err, file=sys.stderr)
            return 2
        if schedule:
            print(_dream_schedule_snippet(sys.platform, bundle, hh, mm))
        else:
            print(_dream_unschedule_snippet(sys.platform, bundle))
        return 0

    from . import dream as _dream
    if getattr(args, "bundle", None):
        bundle = Path(args.bundle)
    else:
        bundle = _resolve_bundle(Path(args.config))
    if bundle is None:
        return 1
    report = _dream.dream_audit(bundle)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        meta = report.get("_meta", {})
        candidates = meta.get("candidate_count", 0)
        print(f"dream audit (read-only) — {candidates} candidate page(s)")
        for section in ("okf_hard_rules", "mneme_writer_rules"):
            items = report.get(section, [])
            if not items:
                continue
            print(f"  {section}:")
            for it in items:
                print(f"    - {it['path']}: [{it['rule']}]")
    return 0


# ---------------------------------------------------------------------------
# dream --schedule / --unschedule snippet helpers
#
# The helper prints a platform-specific scheduler snippet. It NEVER writes
# to ``~/Library/LaunchAgents/``, never edits the user's crontab, and
# never calls ``schtasks`` directly. The user inspects and pastes the
# output. ``sys.platform`` drives the dispatch: ``darwin`` -> launchd,
# ``win32`` -> schtasks, everything else -> crontab.
# ---------------------------------------------------------------------------

_DEFAULT_DREAM_TIME = "02:00"  # 24h HH:MM, matches README
_DREAM_LAUNCHD_DIR = "~/Library/LaunchAgents"
_DREAM_LAUNCHD_LABEL_PREFIX = "mneme.dream"


def _parse_dream_time(value: str | None) -> Tuple[int, int, str | None]:
    """Parse ``HH:MM`` into ``(hour, minute, error)``.

    ``None`` or empty -> default ``02:00``. Returns an error string
    (instead of raising) so the CLI can format it on stderr and exit 2.
    """
    raw = (value or _DEFAULT_DREAM_TIME).strip()
    try:
        hh_s, mm_s = raw.split(":", 1)
        hh, mm = int(hh_s), int(mm_s)
    except (ValueError, AttributeError):
        return 0, 0, f"--time must be HH:MM, got {value!r}"
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return 0, 0, f"--time out of range (00:00..23:59), got {value!r}"
    return hh, mm, None


def _bundle_token(bundle: Path) -> str:
    """Stable short token for ``bundle`` so plist / crontab labels are unique."""
    return hashlib.sha256(str(bundle).encode("utf-8")).hexdigest()[:8]


def _xml_attr(value: str) -> str:
    """Minimal XML attribute escaping for plist snippets."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_launchd_plist(bundle: Path, python_path: str, hh: int, mm: int) -> str:
    label = f"{_DREAM_LAUNCHD_LABEL_PREFIX}.{_bundle_token(bundle)}"
    plist_path = f"{_DREAM_LAUNCHD_DIR}/{label}.plist"
    bundle_x = _xml_attr(str(bundle))
    py_x = _xml_attr(python_path)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{label}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        f"    <string>{py_x}</string>\n"
        "    <string>-m</string>\n"
        "    <string>mneme</string>\n"
        "    <string>dream</string>\n"
        "    <string>--bundle</string>\n"
        f"    <string>{bundle_x}</string>\n"
        "  </array>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n"
        "    <key>Hour</key>\n"
        f"    <integer>{hh}</integer>\n"
        "    <key>Minute</key>\n"
        f"    <integer>{mm}</integer>\n"
        "  </dict>\n"
        "  <key>WorkingDirectory</key>\n"
        f"  <string>{bundle_x}</string>\n"
        "</dict>\n"
        "</plist>\n"
        "\n"
        f"# Save the snippet above as: {plist_path}\n"
        f"# Then load it (run once):  launchctl load {plist_path}\n"
    )


def _render_launchd_unschedule(bundle: Path) -> str:
    label = f"{_DREAM_LAUNCHD_LABEL_PREFIX}.{_bundle_token(bundle)}"
    plist_path = f"{_DREAM_LAUNCHD_DIR}/{label}.plist"
    return (
        f"# Unschedule nightly dream audit for {bundle}:\n"
        f"launchctl unload {plist_path} 2>/dev/null || true\n"
        f"rm {plist_path}\n"
    )


def _render_crontab_line(bundle: Path, python_path: str, hh: int, mm: int) -> str:
    # Preserve a sane PATH so `python3 -m mneme ...` resolves the same
    # interpreter the user just ran in their shell.
    return (
        f"# Mneme nightly dream audit (read-only) — {bundle}\n"
        f"{mm} {hh} * * * {python_path} -m mneme dream --bundle {bundle}\n"
        f"# install:  ( crontab -l 2>/dev/null; "
        f"printf '%s\\n' '<lines above>' ) | crontab -\n"
    )


def _render_crontab_unschedule(bundle: Path) -> str:
    return (
        f"# Remove the Mneme dream audit crontab entry for {bundle}:\n"
        f"crontab -l 2>/dev/null | "
        f"grep -v 'mneme dream --bundle {bundle}' | crontab -\n"
    )


def _render_schtasks(bundle: Path, python_path: str, hh: int, mm: int) -> str:
    time_str = f"{hh:02d}:{mm:02d}"
    return (
        f'schtasks /Create /SC DAILY /TN mneme-dream '
        f'/TR "{python_path} -m mneme dream --bundle {bundle}" '
        f"/ST {time_str}\n"
    )


def _render_schtasks_unschedule() -> str:
    return "schtasks /Delete /TN mneme-dream /F\n"


def _dream_schedule_snippet(platform: str, bundle: Path, hh: int, mm: int) -> str:
    py = sys.executable
    if platform == "darwin":
        return _render_launchd_plist(bundle, py, hh, mm)
    if platform == "win32":
        return _render_schtasks(bundle, py, hh, mm)
    # Linux and other unix-likes -> crontab.
    return _render_crontab_line(bundle, py, hh, mm)


def _dream_unschedule_snippet(platform: str, bundle: Path) -> str:
    if platform == "darwin":
        return _render_launchd_unschedule(bundle)
    if platform == "win32":
        return _render_schtasks_unschedule()
    return _render_crontab_unschedule(bundle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mneme")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="scaffold an OKF bundle")
    init_parser.add_argument("path")
    init_parser.add_argument("--config", default=None)
    init_parser.set_defaults(handler=cmd_init)

    lint_parser = subparsers.add_parser(
        "lint", help="validate the bundle (OKF MUSTs + diagnostics)"
    )
    lint_parser.add_argument("path", nargs="?", default=None)
    lint_parser.add_argument("--bundle", dest="bundle", default=None)
    lint_parser.add_argument("--config", default=None)
    lint_parser.set_defaults(handler=cmd_lint)

    reindex_parser = subparsers.add_parser("reindex", help="rebuild the search index")
    reindex_parser.add_argument("--bundle", dest="bundle", default=None)
    reindex_parser.add_argument("--config", default=None)
    reindex_parser.add_argument(
        "--l2",
        action="store_true",
        help=(
            "opt into the L2 (sqlite-vec + FastEmbed + BGE) index path "
            "instead of the default FTS5 rebuild. Requires "
            "`pip install 'sqlite-vec>=0.1.9,<0.2' 'fastembed>=0.8.0,<0.9'`."
        ),
    )
    reindex_parser.set_defaults(handler=cmd_reindex)

    search_parser = subparsers.add_parser("search", help="return ranked candidates from the index")
    search_parser.add_argument("query", type=_query)
    search_parser.add_argument("-k", "--limit", type=_limit, default=10)
    search_parser.add_argument("--type", dest="concept_type", default=None)
    search_parser.add_argument("--bundle", dest="bundle", default=None)
    search_parser.add_argument("--config", default=None)
    search_parser.add_argument("--json", action="store_true")
    search_parser.add_argument(
        "--l2",
        action="store_true",
        help=(
            "search via L2 (sqlite-vec + FastEmbed + BGE) instead of FTS5. "
            "Requires an index built with `mneme reindex --l2`; errors out "
            "rather than silently falling back to FTS5."
        ),
    )
    search_parser.set_defaults(handler=cmd_search)

    dream_parser = subparsers.add_parser(
        "dream",
        help="read-only audit (writes happen in the SKILL.md workflow, after user approval)",
    )
    dream_parser.add_argument(
        "--bundle",
        dest="bundle",
        default=None,
        help="bundle path (default: resolve via $MNEME_BUNDLE / config.toml)",
    )
    dream_parser.add_argument("--config", default=None)
    dream_parser.add_argument("--json", action="store_true")
    dream_parser.add_argument(
        "--schedule",
        action="store_true",
        help=(
            "print a platform-specific nightly scheduler snippet "
            "(launchd / crontab / schtasks) — does NOT install it"
        ),
    )
    dream_parser.add_argument(
        "--unschedule",
        action="store_true",
        help="print the matching removal snippet (does NOT uninstall)",
    )
    dream_parser.add_argument(
        "--time",
        default=None,
        help="local run time HH:MM for --schedule (default: 02:00)",
    )
    dream_parser.set_defaults(handler=cmd_dream)
    return parser



def main(argv=None) -> int:
    """CLI entry point.

    Accepts an optional ``argv`` list so callers can drive it from Python
    (tests, embedding hosts). When invoked as a console script via the
    ``[project.scripts]`` entry point, setuptools generates a stub that
    calls ``main()`` with no arguments — ``argv=None`` resolves that case
    to ``sys.argv[1:]``.
    """
    import sys
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return args.handler(args)
