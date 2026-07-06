#!/usr/bin/env python3
"""mneme CLI: init / reindex.

The other operations (ingest / query / lint / dream) are SKILL.md-driven
host-agent workflows — they don't need CLI subcommands. This CLI is for
manual / scripted use of the two stateful operations only.
"""
from __future__ import annotations

import sys
from pathlib import Path

CONFIG_DEFAULT = Path.home() / ".config" / "mneme" / "config.toml"


def _write_config(bundle_path: Path, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(f'bundle_path = "{bundle_path}"\n', encoding="utf-8")


def cmd_init(args) -> int:
    if not args:
        print("usage: mneme init <path> [--config <cfg>]", file=sys.stderr)
        return 2
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
    config = Path(args[args.index("--config") + 1]) if "--config" in args else CONFIG_DEFAULT
    sys.path.insert(0, str(Path(__file__).parent))
    from tools_helpers import resolve_bundle
    bundle = resolve_bundle(config_path=config)
    if bundle is None:
        print("no bundle found", file=sys.stderr)
        return 1
    import indexlib
    n = indexlib.reindex_bundle(str(bundle), indexlib.default_embed_fn())
    print(f"indexed {n} concepts into {bundle}/.mneme/index.db")
    return 0


def main(argv) -> int:
    if not argv:
        print("usage: mneme {init|reindex} ...", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    return {"init": cmd_init, "reindex": cmd_reindex}.get(
        cmd, lambda a: (print("unknown command", file=sys.stderr), 2)[1]
    )(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
