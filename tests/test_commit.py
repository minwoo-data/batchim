#!/usr/bin/env python3
"""Tests for 받침 commit.py (FR-S3 single-rename commit): durable runs/<run_id>/,
CURRENT pointer, byte-for-byte verify, idempotency, staging discard, tamper/skip.
Run: python tests/test_commit.py"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import commit as cm           # noqa: E402
import validate_ledger as vl  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def _session():
    d = tempfile.mkdtemp(prefix="batchim_commit_")
    art = os.path.join(d, "artifacts"); os.makedirs(art)
    os.makedirs(os.path.join(d, "sources"))

    def wl(p, rows):
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wl(os.path.join(d, "sources", "sources.jsonl"),
       [{"id": "s1", "quality_rating": "A", "content_hash": "sha256:s", "snapshot_path": "snapshots/s1.txt"},
        {"id": "s2", "quality_rating": "B", "content_hash": "sha256:t", "snapshot_path": "snapshots/s2.txt"}])
    wl(os.path.join(art, "claim_ledger.jsonl"), [{"claim_id": "c1", "text": "x", "claim_text_hash": "sha256:c"}])
    wl(os.path.join(art, "risk_classifications.jsonl"),
       [{"claim_id": "c1", "computed_risk": "high", "atomic": True, "atomized_from": None, "gazetteer_hash": "sha256:g"}])
    wl(os.path.join(art, "entailment_verdicts.jsonl"), [
        {"verdict_id": "v1", "claim_id": "c1", "source_id": "s1", "producer": "verifier", "label": "entails",
         "span_state": "done", "anchors_ok": True, "source_grade": "A", "snapshot_hash": "sha256:s", "claim_text_hash": "sha256:c"},
        {"verdict_id": "v2", "claim_id": "c1", "source_id": "s2", "producer": "verifier", "label": "entails",
         "span_state": "done", "anchors_ok": True, "source_grade": "B", "snapshot_hash": "sha256:t", "claim_text_hash": "sha256:c"}])
    with open(os.path.join(art, "independence_partition.json"), "w", encoding="utf-8") as f:
        json.dump({"clusters": {"s1": "cl_a", "s2": "cl_b"}}, f)
    vl.validate(d, os.path.join(art, "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    return d


def run():
    d = _session()
    cur = json.load(open(os.path.join(d, "CURRENT"), encoding="utf-8"))
    run_id = cur["run_id"]
    check("CURRENT written", run_id.startswith("run_"))
    run_dir = os.path.join(d, "runs", run_id)
    check("durable run dir exists", os.path.isdir(run_dir))
    check("committed verified_claims present", os.path.isfile(os.path.join(run_dir, "verified_claims.json")))
    check("committed manifest present", os.path.isfile(os.path.join(run_dir, "manifest.json")))

    # read_current verifies byte-for-byte
    rd, man = cm.read_current(d)
    check("read_current verifies clean", rd == run_dir and man["run_id"] == run_id)

    # idempotent: re-running validate yields the same run_id, no error
    vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    cur2 = json.load(open(os.path.join(d, "CURRENT"), encoding="utf-8"))
    check("idempotent re-commit -> same run_id", cur2["run_id"] == run_id)

    # leftover .staging is discarded on next commit (crash recovery)
    os.makedirs(os.path.join(d, "runs", ".staging"), exist_ok=True)
    with open(os.path.join(d, "runs", ".staging", "junk"), "w") as f:
        f.write("partial")
    vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("leftover .staging discarded", not os.path.isdir(os.path.join(d, "runs", ".staging")))

    # tamper the committed output -> read_current detects byte drift
    with open(os.path.join(run_dir, "verified_claims.json"), "a", encoding="utf-8") as f:
        f.write(" ")
    try:
        cm.read_current(d); ok = False
    except ValueError as e:
        ok = "drift" in str(e)
    check("tampered committed output -> raises drift", ok)
    # restore for next checks
    shutil.rmtree(d, ignore_errors=True)

    # CURRENT points to a missing run -> incomplete commit
    d2 = _session()
    json.dump({"run_id": "run_doesnotexist", "signature": "sha256:x"},
              open(os.path.join(d2, "CURRENT"), "w"))
    try:
        cm.read_current(d2); ok = False
    except ValueError as e:
        ok = "missing" in str(e) or "incomplete" in str(e)
    check("CURRENT -> missing run -> raises", ok)

    # no CURRENT at all -> skip
    d3 = tempfile.mkdtemp(prefix="batchim_commit3_")
    try:
        cm.read_current(d3); ok = False
    except ValueError as e:
        ok = "absent" in str(e)
    check("no CURRENT -> raises absent", ok)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
