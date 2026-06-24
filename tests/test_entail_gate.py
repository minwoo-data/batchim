#!/usr/bin/env python3
"""Tests for 받침 entail_gate.py: anchors application, bindings, high-risk filter,
failed/unknown-label handling, snapshot-hash binding, and end-to-end consistency
with decide.py. Runs standalone: `python tests/test_entail_gate.py`."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import decide        # noqa: E402
import entail_gate   # noqa: E402
import snapshot      # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


SNAP = "The Act prohibits real-time biometric ID. Revenue grew to $4.2bn in 2026."


def _claim(cid="clm_001", text="Revenue grew to 4.2bn in 2026"):
    return {"claim_id": cid, "text": text, "claim_text_hash": "sha256:deadbeef"}


def _source(sid="src_001", grade="A"):
    return {"id": sid, "quality_rating": grade, "content_hash": snapshot.content_hash(SNAP),
            "snapshot_path": f"snapshots/{sid}.txt"}


def test_build_entails_anchored():
    raw = {"claim_id": "clm_001", "source_id": "src_001", "label": "entails",
           "evidence_span": "grew to $4.2bn in 2026", "span_state": "done",
           "model_id": "m1", "verifier_prompt_hash": "sha256:p"}
    v = entail_gate.build_verdict(_claim(), _source(), raw, SNAP)
    check("entails: span_matched", v["span_matched"])
    check("entails: numeric_ok ($4.2bn/2026)", v["numeric_ok"])
    check("entails: anchors_ok", v["anchors_ok"])
    check("entails: coords re-extract to normalized span (FR-A5)",
          v["span_char_start"] >= 0 and v["span_char_end"] > v["span_char_start"])
    check("entails: bound to snapshot_hash", v["snapshot_hash"] == _source()["content_hash"])
    check("entails: bound to claim_text_hash", v["claim_text_hash"] == "sha256:deadbeef")
    check("entails: source_grade copied", v["source_grade"] == "A")
    check("entails: producer=verifier", v["producer"] == "verifier")


def test_fabricated_span_fails_anchor():
    raw = {"claim_id": "clm_001", "source_id": "src_001", "label": "entails",
           "evidence_span": "a total nationwide ban with no exceptions", "span_state": "done"}
    v = entail_gate.build_verdict(_claim(text="the act bans everything"), _source(), raw, SNAP)
    check("fabricated: span not matched", not v["span_matched"])
    check("fabricated: anchors_ok False", not v["anchors_ok"])


def test_number_swap_fails_anchor():
    raw = {"claim_id": "clm_001", "source_id": "src_001", "label": "entails",
           "evidence_span": "grew to $4.2bn in 2026", "span_state": "done"}
    # claim asserts 5.0bn but span/snapshot say 4.2bn -> numeric anchor catches swap
    v = entail_gate.build_verdict(_claim(text="revenue was 5.0bn in 2026"), _source(), raw, SNAP)
    check("number-swap: span matched but numeric_ok False", v["span_matched"] and not v["numeric_ok"])
    check("number-swap: anchors_ok False", not v["anchors_ok"])


def test_failed_state_not_anchored():
    raw = {"claim_id": "clm_001", "source_id": "src_001", "label": "neutral",
           "evidence_span": "", "span_state": "failed", "fail_reason": "timeout"}
    v = entail_gate.build_verdict(_claim(), _source(), raw, SNAP)
    check("failed: span_state preserved", v["span_state"] == "failed")
    check("failed: anchors_ok False", not v["anchors_ok"])


def test_unknown_label_failclosed():
    raw = {"claim_id": "clm_001", "source_id": "src_001", "label": "maybe",
           "evidence_span": "grew to $4.2bn in 2026", "span_state": "done"}
    v = entail_gate.build_verdict(_claim(), _source(), raw, SNAP)
    check("unknown label: validation_error set", v["validation_error"] is not None)
    check("unknown label: fail-closed to failed", v["span_state"] == "failed")
    check("unknown label: cannot anchor", not v["anchors_ok"])


def _session(claims, risk, sources, raws):
    d = tempfile.mkdtemp(prefix="batchim_gate_")
    art = os.path.join(d, "artifacts")
    os.makedirs(art, exist_ok=True)
    os.makedirs(os.path.join(d, "sources"), exist_ok=True)
    os.makedirs(os.path.join(d, "snapshots"), exist_ok=True)

    def w(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    w(os.path.join(art, "claim_ledger.jsonl"), claims)
    w(os.path.join(art, "risk_classifications.jsonl"), risk)
    w(os.path.join(d, "sources", "sources.jsonl"), sources)
    w(os.path.join(art, "raw_verdicts.jsonl"), raws)
    for s in sources:
        with open(os.path.join(d, "snapshots", f"{s['id']}.txt"), "w", encoding="utf-8") as f:
            f.write(SNAP)
    return d


def test_run_high_risk_filter_and_chain():
    claims = [_claim("clm_hi"), _claim("clm_lo")]
    risk = [{"claim_id": "clm_hi", "computed_risk": "high"},
            {"claim_id": "clm_lo", "computed_risk": "normal"}]
    sources = [_source("src_001", "A"), _source("src_002", "B")]
    raws = [
        {"claim_id": "clm_hi", "source_id": "src_001", "label": "entails",
         "evidence_span": "grew to $4.2bn in 2026", "span_state": "done", "model_id": "m"},
        {"claim_id": "clm_hi", "source_id": "src_002", "label": "entails",
         "evidence_span": "grew to $4.2bn in 2026", "span_state": "done", "model_id": "m"},
        {"claim_id": "clm_lo", "source_id": "src_001", "label": "entails",
         "evidence_span": "grew to $4.2bn in 2026", "span_state": "done", "model_id": "m"},
    ]
    d = _session(claims, risk, sources, raws)
    verdicts, errors = entail_gate.run(d)
    check("run: no errors", not errors)
    check("run: low-risk claim filtered out", all(v["claim_id"] == "clm_hi" for v in verdicts))
    check("run: 2 verdicts for high-risk claim", len(verdicts) == 2)

    # feed into decide.py as validate_ledger would (distinct clusters + A/B) -> verified
    clusters = {"src_001": "cl_a", "src_002": "cl_b"}
    tuples = [{"normalized_verdict": v["label"], "anchors_ok": v["anchors_ok"],
               "cluster_id": clusters[v["source_id"]], "quality_rating": v["source_grade"],
               "source_id": v["source_id"]} for v in verdicts]
    r = decide.decide_claim("clm_hi", tuples)
    check("chain: entail_gate -> decide => verified", r["status"] == "verified" and r["independent_entails"] == 2)


def test_run_snapshot_hash_mismatch_errors():
    claims = [_claim("clm_hi")]
    risk = [{"claim_id": "clm_hi", "computed_risk": "high"}]
    src = _source("src_001", "A")
    src["content_hash"] = "sha256:0000"  # wrong hash vs the SNAP file on disk
    raws = [{"claim_id": "clm_hi", "source_id": "src_001", "label": "entails",
             "evidence_span": "grew to $4.2bn in 2026", "span_state": "done"}]
    d = _session(claims, risk, [src], raws)
    _, errors = entail_gate.run(d)
    check("hash mismatch: binding error reported", any("mismatch" in e for e in errors))


if __name__ == "__main__":
    test_build_entails_anchored()
    test_fabricated_span_fails_anchor()
    test_number_swap_fails_anchor()
    test_failed_state_not_anchored()
    test_unknown_label_failclosed()
    test_run_high_risk_filter_and_chain()
    test_run_snapshot_hash_mismatch_errors()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
