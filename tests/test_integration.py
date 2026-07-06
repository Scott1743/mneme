import subprocess
import sys
from pathlib import Path

import mneme
import indexlib
from test_indexlib import fake_embed

_E = lambda ts: fake_embed(ts, 8)


def test_end_to_end_init_reindex_search_validate(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    bundle = tmp_path / "wiki"
    assert mneme.main(["init", str(bundle), "--config", str(cfg)]) == 0
    # manually write a concept (simulating an ingest)
    c = bundle / "concepts" / "cats.md"
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text("---\ntype: Concept\ntitle: Cats\ndescription: felines\n---\n# Cats\nCats love naps in the sun.\n")
    # reindex with fake embed
    monkeypatch.setattr(indexlib, "default_embed_fn", lambda: _E)
    assert mneme.main(["reindex", "--config", str(cfg)]) == 0
    # search
    conn = indexlib.open_index(bundle / ".mneme" / "index.db")
    res = indexlib.search(conn, "Cats love naps in the sun.", 1, _E)
    assert res and res[0]["concept_id"] == "concepts/cats"
    conn.close()
    # validate
    v = Path(__file__).parent.parent / "skills" / "mneme" / "scripts" / "validate_okf.py"
    r = subprocess.run([sys.executable, str(v), str(bundle)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout