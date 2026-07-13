import json
import subprocess
import sys
from pathlib import Path

from mneme import indexlib
import mneme
from test_indexlib import _E, write_concept
import pytest
pytestmark = pytest.mark.integration


def test_end_to_end_init_reindex_search_validate(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    assert mneme.main(["init", str(bundle), "--config", str(cfg)]) == 0
    capsys.readouterr()
    write_concept(bundle, "concepts/cats.md", "Cats", "Cats love naps in the sun.")
    write_concept(bundle, "archive/old-cats.md", "Old Cats", "Retired cat note.")

    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: _E)
    assert mneme.main(["reindex", "--config", str(cfg)]) == 0
    capsys.readouterr()
    assert mneme.main(["search", "Cats love naps in the sun.", "-k", "1", "--json", "--config", str(cfg)]) == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits[0]["concept_id"] == "concepts/cats"
    assert (bundle / hits[0]["path"]).is_file()
    assert all(hit["concept_id"] != "archive/old-cats" for hit in hits)

    validator = Path(__file__).parent.parent / "skills" / "mneme" / "scripts" / "mneme" / "validate_okf.py"
    result = subprocess.run(
        [sys.executable, str(validator), str(bundle)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout
