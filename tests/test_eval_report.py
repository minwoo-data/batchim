#!/usr/bin/env python3
"""Tests for 받침 eval_report.py (§9 hard gate, new-schema aligned).
Run: python tests/test_eval_report.py"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import eval_report as er      # noqa: E402
import validate_ledger as vl  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


C1_TEXT = "QUIC requires TLS version 1.3 or greater as its handshake protocol."


def _session(body):
    d = tempfile.mkdtemp(prefix="batchim_eval_")
    art = os.path.join(d, "artifacts"); os.makedirs(art)
    os.makedirs(os.path.join(d, "sources"))
    os.makedirs(os.path.join(d, "outputs"))

    def wl(p, rows):
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wl(os.path.join(d, "sources", "sources.jsonl"),
       [{"id": "src_001", "quality_rating": "A", "content_hash": "sha256:s", "snapshot_path": "snapshots/src_001.txt"},
        {"id": "src_002", "quality_rating": "B", "content_hash": "sha256:t", "snapshot_path": "snapshots/src_002.txt"}])
    wl(os.path.join(art, "claim_ledger.jsonl"),
       [{"claim_id": "c1", "text": C1_TEXT, "claim_text_hash": "sha256:c"},
        {"claim_id": "c2", "text": "HTTP/3 allows a TLS 1.2 fallback for legacy compatibility.", "claim_text_hash": "sha256:c2"}])
    wl(os.path.join(art, "risk_classifications.jsonl"),
       [{"claim_id": "c1", "computed_risk": "high", "atomic": True, "atomized_from": None},
        {"claim_id": "c2", "computed_risk": "high", "atomic": True, "atomized_from": None}])
    wl(os.path.join(art, "entailment_verdicts.jsonl"), [
        {"claim_id": "c1", "source_id": "src_001", "producer": "verifier", "label": "entails", "span_state": "done",
         "anchors_ok": True, "span_matched": True, "source_grade": "A", "snapshot_hash": "sha256:s", "claim_text_hash": "sha256:c"},
        {"claim_id": "c1", "source_id": "src_002", "producer": "verifier", "label": "entails", "span_state": "done",
         "anchors_ok": True, "span_matched": True, "source_grade": "B", "snapshot_hash": "sha256:t", "claim_text_hash": "sha256:c"},
        {"claim_id": "c2", "source_id": "src_001", "producer": "verifier", "label": "neutral", "span_state": "done",
         "anchors_ok": False, "span_matched": False, "source_grade": "A", "snapshot_hash": "sha256:s", "claim_text_hash": "sha256:c2"}])
    with open(os.path.join(art, "independence_partition.json"), "w", encoding="utf-8") as f:
        json.dump({"clusters": {"src_001": "cl_a", "src_002": "cl_b"}}, f)
    vl.validate(d, os.path.join(art, "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    with open(os.path.join(d, "outputs", "report.md"), "w", encoding="utf-8") as f:
        f.write(body)
    return d


def run():
    # clean: body asserts the verified claim c1, cites both registry sources, no leak
    body = f"Per the standard, {C1_TEXT} [src_001][src_002]"
    d = _session(body)
    rep = er.evaluate(d)
    check("clean -> PASS", rep["verdict"] == "PASS")
    check("c1 counted high-risk verified", rep["counts"]["high_risk_verified"] == 1)
    check("missing_entailment_proof = 0", rep["metrics"]["missing_entailment_proof_rate"] == 0.0)
    check("span_match = 100%", rep["metrics"]["span_match_rate"] == 1.0)
    check("coverage_ok (c1 verified, c2 unresolved both have status)", rep["coverage_ok"])
    check("verified_coverage = 100%", rep["metrics"]["verified_coverage_rate"] == 1.0)
    check("manifest_ok (signed + not superseded)", rep["manifest_ok"])
    check("citation_resolution = 100%", rep["metrics"]["citation_resolution_rate"] == 1.0)

    # leak: the unresolved claim c2's text appears assertively in the body
    leak_body = body + "\nNote: HTTP/3 allows a TLS 1.2 fallback for legacy compatibility. [src_001]"
    d2 = _session(leak_body)
    rep = er.evaluate(d2)
    check("leak -> FAIL", rep["verdict"] == "FAIL" and rep["counts"]["leaks"] == 1)

    # dangling citation: body cites a source not in the registry
    d3 = _session(body + " [src_999]")
    rep = er.evaluate(d3)
    check("dangling citation -> FAIL", rep["verdict"] == "FAIL" and "src_999" in rep["dangling_citations"])

    # unsigned: remove CURRENT -> manifest gate fails
    d4 = _session(body)
    os.remove(os.path.join(d4, "CURRENT"))
    rep = er.evaluate(d4)
    check("no CURRENT -> manifest_ok False -> FAIL", not rep["manifest_ok"] and rep["verdict"] == "FAIL")


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
