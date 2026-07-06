#!/usr/bin/env python3
"""mneme CLI: init / reindex / ingest / query / lint."""
from __future__ import annotations

import sys
from pathlib import Path

CONFIG_DEFAULT = Path.home() / ".config" / "mneme" / "config.toml"


def _write_config(bundle_path: Path, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f'bundle_path = "{bundle_path}"\n', encoding="utf-8")


def cmd_init(args) -> int:
    bundle = Path(args[0])
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "sources").mkdir(exist_ok=True)
    (bundle / "sources" / ".gitkeep").write_text("")
    if not (bundle / "index.md").exists():
        (bundle / "index.md").write_text('---\nokf_version: "0.1"\n---\n\n# Concepts\n', encoding="utf-8")
    if not (bundle / "log.md").exists():
        (bundle / "log.md").write_text("# Directory Update Log\n", encoding="utf-8")
    _write_config(bundle, config)
    print(f"initialized bundle at {bundle}; recorded in {config}")
    return 0


def cmd_reindex(args) -> int:
    import indexlib
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    from tools import resolve_bundle
    bundle = resolve_bundle(config_path=config)
    if bundle is None:
        print("no bundle found", file=sys.stderr)
        return 1
    n = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
    print(f"indexed {n} concepts into {bundle}/.mneme/index.db")
    return 0


def cmd_ingest(args) -> int:
    from ingest import run as run_ingest
    return run_ingest(args)


def cmd_query(args) -> int:
    from query import run as run_query
    return run_query(args)


def cmd_lint(args) -> int:
    from lint import run as run_lint
    return run_lint(args)


def main(argv) -> int:
    if not argv:
        print("usage: mneme {init|reindex|ingest|query|lint} ...", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    return {"init": cmd_init, "reindex": cmd_reindex, "ingest": cmd_ingest,
            "query": cmd_query, "lint": cmd_lint}.get(
        cmd, lambda a: (print("unknown command", file=sys.stderr), 2)[1]
    )(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
