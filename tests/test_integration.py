import json
import subprocess
import sys
from pathlib import Path

from mneme import indexlib
import mneme
from test_indexlib import write_concept
import pytest
pytestmark = pytest.mark.integration


def test_end_to_end_init_reindex_search_validate(tmp_path, monkeypatch, capsys):
    """End-to-end smoke: init -> FTS5 reindex -> FTS5 search -> validate.

    v2.0 no longer wires ``mneme reindex`` to the L2 (sqlite-vec /
    fastembed) path; the CLI's reindex command stays L2-only for the
    deferred v2.1 path, but the v2.0 user-facing search runs against
    the FTS5 index built by :func:`indexlib.reindex_paths`. This
    integration test exercises that v2.0 contract end-to-end.
    """
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    assert mneme.main(["init", str(bundle), "--config", str(cfg)]) == 0
    capsys.readouterr()
    cats = write_concept(bundle, "concepts/cats.md", "Cats", "Cats love naps in the sun.")
    write_concept(bundle, "archive/old-cats.md", "Old Cats", "Retired cat note.")

    # Build the FTS5 index (v2.0 search surface) directly. The CLI
    # reindex command still wires to the L2 path which is deferred to
    # v2.1; the v2.0 search relies on the FTS5 index built here.
    indexlib.reindex_paths([cats, bundle / "archive" / "old-cats.md"], bundle)
    capsys.readouterr()

    assert mneme.main(
        ["search", "Cats love naps", "-k", "1", "--json", "--config", str(cfg)]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    candidates = payload["candidates"]
    assert candidates, f"expected at least one FTS5 candidate; got {payload!r}"
    top = candidates[0]
    assert top["path"] == "concepts/cats.md"
    assert (bundle / top["path"]).is_file()

    validator = Path(__file__).parent.parent / "skills" / "mneme" / "scripts" / "mneme" / "validate_okf.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(bundle)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout
