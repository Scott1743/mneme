from pathlib import Path

from scripts.bootstrap_dogfood import _source_records


def test_source_records_preserves_all_files_with_normalized_name_collisions():
    records = _source_records(
        [Path("001_shared.md"), Path("002_shared.md"), Path("other.md")]
    )

    assert [slug for _, slug in records] == ["shared", "shared--2", "other"]
    assert len({slug for _, slug in records}) == len(records)
