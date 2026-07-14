import json
import subprocess
import sys
from pathlib import Path

from mneme import indexlib
import mneme
import pytest
pytestmark = pytest.mark.integration


def write_concept(bundle: Path, relative: str, title: str, body: str) -> Path:
    path = bundle / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: Concept\ntitle: {title}\ntags: [test]\n---\n{body}\n",
        encoding="utf-8",
    )
    return path


def test_end_to_end_init_reindex_search_validate(tmp_path, monkeypatch, capsys):
    """End-to-end smoke: init -> FTS5 reindex -> FTS5 search -> validate.

    The v2.0 CLI rebuilds and searches the FTS5 index with no optional
    runtime dependencies. This integration test exercises that contract.
    """
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    assert mneme.main(["init", str(bundle), "--config", str(cfg)]) == 0
    capsys.readouterr()
    cats = write_concept(bundle, "concepts/cats.md", "Cats", "Cats love naps in the sun.")
    write_concept(bundle, "archive/old-cats.md", "Old Cats", "Retired cat note.")

    assert mneme.main(["reindex", "--config", str(cfg)]) == 0
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
