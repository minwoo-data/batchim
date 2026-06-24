#!/usr/bin/env python3
"""Tests for 받침 snapshot.py: freeze + hash + idempotency + binding to
anchors.span_match. Runs standalone: `python tests/test_snapshot.py`."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import anchors    # noqa: E402
import snapshot   # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _session(rows):
    d = tempfile.mkdtemp(prefix="batchim_snap_")
    sp = os.path.join(d, "sources", "sources.jsonl")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    with open(sp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return d, sp


def test_hash_stable_and_line_endings():
    # content_hash is line-ending-independent (cross-platform stable)
    check("hash: \\r\\n == \\n", snapshot.content_hash("a\r\nb") == snapshot.content_hash("a\nb"))
    check("hash: prefixed sha256:", snapshot.content_hash("x").startswith("sha256:"))
    check("hash: differs on content", snapshot.content_hash("a") != snapshot.content_hash("b"))


def test_freeze_inline():
    text = "The Act prohibits real-time biometric ID. Revenue grew to $4.2bn in 2026."
    d, sp = _session([{"id": "src_001", "url": "http://x", "text": text, "schema_version": 1}])
    rows, errors = snapshot.freeze(d, sp)
    check("freeze: no errors", not errors)
    row = rows[0]
    check("freeze: snapshot_path set (POSIX)", row.get("snapshot_path") == "snapshots/src_001.txt")
    check("freeze: content_hash set", str(row.get("content_hash", "")).startswith("sha256:"))
    check("freeze: inline text dropped", "text" not in row)
    # snapshot file exists with faithful (line-normalized) content
    snap_file = os.path.join(d, "snapshots", "src_001.txt")
    check("freeze: snapshot file written", os.path.isfile(snap_file))
    with open(snap_file, encoding="utf-8") as f:
        stored = f.read()
    check("freeze: stored hash matches row", snapshot.content_hash(stored) == row["content_hash"])
    # the frozen snapshot is what anchors matches against
    m, *_ = anchors.span_match("real-time biometric ID", stored)
    check("freeze: span_match works on snapshot", m)


def test_freeze_raw_path():
    d = tempfile.mkdtemp(prefix="batchim_snap_")
    raw = os.path.join(d, "raw", "a.txt")
    os.makedirs(os.path.dirname(raw), exist_ok=True)
    with open(raw, "w", encoding="utf-8") as f:
        f.write("frozen body text")
    sp = os.path.join(d, "sources", "sources.jsonl")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    with open(sp, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "src_002", "raw_path": os.path.join("raw", "a.txt"), "schema_version": 1}) + "\n")
    rows, errors = snapshot.freeze(d, sp)
    check("raw_path: no errors", not errors)
    check("raw_path: hashed", str(rows[0].get("content_hash", "")).startswith("sha256:"))


def test_idempotent():
    d, sp = _session([{"id": "src_001", "url": "http://x", "text": "hello world", "schema_version": 1}])
    rows1, _ = snapshot.freeze(d, sp)
    snapshot._write_jsonl(sp, rows1)
    h1 = rows1[0]["content_hash"]
    rows2, errors = snapshot.freeze(d, sp)  # second run, snapshot already present
    check("idempotent: no errors", not errors)
    check("idempotent: hash unchanged", rows2[0]["content_hash"] == h1)


def test_missing_text_errors():
    d, sp = _session([{"id": "src_003", "url": "http://x", "schema_version": 1}])
    rows, errors = snapshot.freeze(d, sp)
    check("missing text: error reported", any("src_003" in e for e in errors))


def test_duplicate_id_errors():
    d, sp = _session([
        {"id": "dup", "text": "a", "schema_version": 1},
        {"id": "dup", "text": "b", "schema_version": 1},
    ])
    _, errors = snapshot.freeze(d, sp)
    check("dup id: error reported", any("duplicate" in e for e in errors))


if __name__ == "__main__":
    test_hash_stable_and_line_endings()
    test_freeze_inline()
    test_freeze_raw_path()
    test_idempotent()
    test_missing_text_errors()
    test_duplicate_id_errors()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
