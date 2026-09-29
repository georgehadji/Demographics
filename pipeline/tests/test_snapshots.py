from datetime import UTC, datetime

import pytest

from grpop import snapshots

SRC = "eurostat_demo_find"
URL = "https://example.org/x"
T1 = datetime(2026, 1, 1, tzinfo=UTC)
T2 = datetime(2026, 2, 1, tzinfo=UTC)


def put(root, data, t=T1, source_id=SRC):
    return snapshots.put(root, data, source_id=source_id, source_url=URL, retrieved_at=t)


def test_same_content_same_hash_and_second_write_changes_nothing(tmp_path):
    first = put(tmp_path, b"a")
    manifest = (tmp_path / "manifest.jsonl").read_bytes()
    assert put(tmp_path, b"a", T2) == first
    assert (tmp_path / "manifest.jsonl").read_bytes() == manifest
    assert snapshots.read(tmp_path, first.sha256) == b"a"


def test_revision_is_a_new_version_not_a_replacement(tmp_path):
    a, b, a_again = put(tmp_path, b"a"), put(tmp_path, b"b", T2), put(tmp_path, b"a", T2)
    assert snapshots.history(tmp_path, SRC) == [a, b, a_again]
    assert a_again.sha256 == a.sha256 and a_again.retrieved_at == T2
    assert snapshots.read(tmp_path, a.sha256) == b"a"


def test_corrupt_object_is_detected_not_overwritten(tmp_path):
    snap = put(tmp_path, b"a")
    (tmp_path / "objects" / snap.sha256).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="corrupt"):
        snapshots.read(tmp_path, snap.sha256)
    with pytest.raises(ValueError, match="corrupt"):
        put(tmp_path, b"a", source_id="eurostat_demo_pjan")


def test_rejects_unknown_source_and_naive_time(tmp_path):
    with pytest.raises(KeyError):
        put(tmp_path, b"a", source_id="nope")
    with pytest.raises(ValueError, match="timezone"):
        put(tmp_path, b"a", datetime(2026, 1, 1))
