#!/usr/bin/env python3
"""Tests for 받침 validate_ledger.py: §6.7 join+decide, FR-A5 binding (exit 2),
cite-write passthrough, compound fail-closed, and a full snapshot→classify→
entail_gate→validate chain. Runs standalone: `python tests/test_validate_ledger.py`."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import validate_ledger as vl  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def _mk(sources, claims, risk, verdicts, partition=None, panel=None):
    d = tempfile.mkdtemp(prefix="batchim_vl_")
    art = os.path.join(d, "artifacts")
    os.makedirs(art, exist_ok=True)
    os.makedirs(os.path.join(d, "sources"), exist_ok=True)

    def wl(path, rows):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wl(os.path.join(d, "sources", "sources.jsonl"), sources)
    wl(os.path.join(art, "claim_ledger.jsonl"), claims)
    wl(os.path.join(art, "risk_classifications.jsonl"), risk)
    wl(os.path.join(art, "entailment_verdicts.jsonl"), verdicts)
    if partition is not None:
        with open(os.path.join(art, "independence_partition.json"), "w", encoding="utf-8") as f:
            json.dump(partition, f)
    if panel is not None:  # {claim_id: consensus} -> panel_consensus.jsonl (enables M2)
        wl(os.path.join(art, "panel_consensus.jsonl"),
           [{"claim_id": k, "panel_consensus": v, "schema_version": 1} for k, v in panel.items()])
    return d


def _src(sid, grade, snap="sha256:s"):
    return {"id": sid, "quality_rating": grade, "content_hash": snap}


def _claim(cid, cth="sha256:c"):
    return {"claim_id": cid, "text": f"claim {cid}", "claim_text_hash": cth}


def _risk(cid, risk="high", atomic=True):
    return {"claim_id": cid, "computed_risk": risk, "atomic": atomic, "atomized_from": None}


def _v(cid, sid, label, grade, snap="sha256:s", anchors=True, cth="sha256:c", state="done"):
    return {"verdict_id": f"v_{cid}_{sid}", "claim_id": cid, "source_id": sid,
            "producer": "verifier", "label": label, "span_state": state,
            "anchors_ok": anchors, "source_grade": grade, "snapshot_hash": snap,
            "claim_text_hash": cth}


def _outputs(d):
    with open(os.path.join(d, "outputs", "verified_claims.json"), encoding="utf-8") as f:
        return json.load(f)


def test_verified_two_independent_clusters():
    d = _mk(
        [_src("s1", "A"), _src("s2", "B")],
        [_claim("c1")],
        [_risk("c1")],
        [_v("c1", "s1", "entails", "A"), _v("c1", "s2", "entails", "B")],
        partition={"clusters": {"s1": "cl_a", "s2": "cl_b"}},
    )
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("verified: exit 0", rc == 0)
    out = _outputs(d)
    rec = next(r for r in out if r["claim_id"] == "c1")
    check("verified: status verified", rec["status"] == "verified" and rec["independent_entails"] == 2)


def test_same_cluster_not_verified():
    d = _mk(
        [_src("s1", "A"), _src("s2", "B")],
        [_claim("c1")], [_risk("c1")],
        [_v("c1", "s1", "entails", "A"), _v("c1", "s2", "entails", "B")],
        partition={"clusters": {"s1": "cl_x", "s2": "cl_x"}},  # same cluster = fake independence
    )
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("same-cluster: exit 1 (0 verified)", rc == 1)


def test_ab_contradiction_refuted():
    d = _mk(
        [_src("s1", "A"), _src("s2", "B"), _src("s3", "A")],
        [_claim("c1")], [_risk("c1")],
        [_v("c1", "s1", "entails", "A"), _v("c1", "s2", "entails", "B"),
         _v("c1", "s3", "contradicts", "A")],
        partition={"clusters": {"s1": "cl_a", "s2": "cl_b", "s3": "cl_c"}},
    )
    vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    refuted = json.load(open(os.path.join(d, "outputs", "refuted_claims.json"), encoding="utf-8"))
    check("refuted: A/B contradiction dominates", any(r["claim_id"] == "c1" for r in refuted))


def test_anchor_failed_entails_drops_to_neutral():
    d = _mk(
        [_src("s1", "A"), _src("s2", "B")],
        [_claim("c1")], [_risk("c1")],
        [_v("c1", "s1", "entails", "A", anchors=False), _v("c1", "s2", "entails", "B")],
        partition={"clusters": {"s1": "cl_a", "s2": "cl_b"}},
    )
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("anchor-failed: not verified (exit 1)", rc == 1)


def test_cite_write_non_high_risk():
    d = _mk([_src("s1", "A")], [_claim("c1")], [_risk("c1", risk="normal")], [])
    vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    out = _outputs(d)
    rec = next(r for r in out if r["claim_id"] == "c1")
    check("cite_write: non-high-risk passthrough", rec["status"] == "cite_write" and rec["high_risk"] is False)


def test_compound_fail_closed():
    d = _mk([_src("s1", "A")], [_claim("c1")], [_risk("c1", atomic=False)],
            [_v("c1", "s1", "entails", "A")])
    vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    unresolved = json.load(open(os.path.join(d, "outputs", "unresolved_claims.json"), encoding="utf-8"))
    check("compound: fail-closed needs_atomization",
          any(r["claim_id"] == "c1" and r["status_reason"] == "needs_atomization" for r in unresolved))


def _verified_candidate(panel):
    """A claim M1 would verify (2 entails, distinct A/B clusters), plus a panel."""
    return _mk(
        [_src("s1", "A"), _src("s2", "B")],
        [_claim("c1")], [_risk("c1")],
        [_v("c1", "s1", "entails", "A"), _v("c1", "s2", "entails", "B")],
        partition={"clusters": {"s1": "cl_a", "s2": "cl_b"}},
        panel=panel,
    )


def test_m2_panel_entails_keeps_verified():
    d = _verified_candidate({"c1": "entails"})
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    out = _outputs(d)
    check("M2 panel entails -> still verified", rc == 0 and any(r["claim_id"] == "c1" and r["status"] == "verified" for r in out))


def test_m2_panel_quarantines_quotemine():
    # the hard quote-mine: M1 would verify, but panel refute-lens -> contradicts consensus
    d = _verified_candidate({"c1": "contradicts"})
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    un = json.load(open(os.path.join(d, "outputs", "unresolved_claims.json"), encoding="utf-8"))
    check("M2 panel contradicts -> quarantined (not verified)",
          rc == 1 and any(r["claim_id"] == "c1" and r["status_reason"] == "panel_no_consensus" for r in un))


def test_m2_no_consensus_quarantines():
    d = _verified_candidate({"c1": "no_consensus"})
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("M2 1-1-1 no_consensus -> not verified", rc == 1)


def test_binding_snapshot_hash_mismatch_exit2():
    d = _mk([_src("s1", "A", snap="sha256:REGISTRY")], [_claim("c1")], [_risk("c1")],
            [_v("c1", "s1", "entails", "A", snap="sha256:WRONG")])
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("binding: snapshot_hash mismatch -> exit 2", rc == 2)


def test_binding_grade_copy_disagree_exit2():
    d = _mk([_src("s1", "A")], [_claim("c1")], [_risk("c1")],
            [_v("c1", "s1", "entails", "B")])  # verdict copy says B, registry says A
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("binding: grade copy disagree -> exit 2", rc == 2)


def test_missing_verdict_unresolved_missing():
    d = _mk([_src("s1", "A")], [_claim("c1")], [_risk("c1")], [])  # high-risk, no verdicts
    rc = vl.validate(d, os.path.join(d, "artifacts", "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    unresolved = json.load(open(os.path.join(d, "outputs", "unresolved_claims.json"), encoding="utf-8"))
    check("missing: high-risk w/ no verdict -> unresolved/missing",
          rc == 1 and any(r["claim_id"] == "c1" and r["status_reason"] == "missing" for r in unresolved))


def test_full_chain_snapshot_classify_gate_validate():
    """End-to-end: build inputs, run all four scripts, expect c1 verified."""
    import snapshot, classify_risk, entail_gate
    SNAP1 = "Revenue grew to $4.2bn in 2026."
    SNAP2 = "Confirmed: revenue grew to $4.2bn in 2026."
    d = tempfile.mkdtemp(prefix="batchim_e2e_")
    art = os.path.join(d, "artifacts"); os.makedirs(art)
    os.makedirs(os.path.join(d, "sources"))

    def wl(p, rows):
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    wl(os.path.join(d, "sources", "sources.jsonl"), [
        {"id": "s1", "url": "http://a", "text": SNAP1, "quality_rating": "A", "schema_version": 1},
        {"id": "s2", "url": "http://b", "text": SNAP2, "quality_rating": "B", "schema_version": 1}])
    ledger = [{"claim_id": "c1", "text": "Revenue grew to 4.2bn in 2026", "claim_text_hash": "sha256:c", "schema_version": 1}]
    wl(os.path.join(art, "claim_ledger.jsonl"), ledger)
    with open(os.path.join(art, "independence_partition.json"), "w", encoding="utf-8") as f:
        json.dump({"clusters": {"s1": "cl_a", "s2": "cl_b"}}, f)
    wl(os.path.join(art, "raw_verdicts.jsonl"), [
        {"claim_id": "c1", "source_id": "s1", "label": "entails", "evidence_span": "grew to $4.2bn in 2026", "span_state": "done", "model_id": "m"},
        {"claim_id": "c1", "source_id": "s2", "label": "entails", "evidence_span": "grew to $4.2bn in 2026", "span_state": "done", "model_id": "m"}])

    sources_path = os.path.join(d, "sources", "sources.jsonl")
    rows, _ = snapshot.freeze(d, sources_path)            # freeze + hash
    snapshot._write_jsonl(sources_path, rows)
    wl(os.path.join(art, "risk_classifications.jsonl"),   # deterministic risk
       [r for c in ledger for r in classify_risk.classify_claim(c, classify_risk._gazetteer_hash())])
    verdicts, _ = entail_gate.run(d)                      # anchors + bound verdicts
    entail_gate._write_jsonl(os.path.join(art, "entailment_verdicts.jsonl"), verdicts)

    rc = vl.validate(d, os.path.join(art, "claim_ledger.jsonl"),
                     os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    check("e2e: chain produces exit 0", rc == 0)
    out = json.load(open(os.path.join(d, "outputs", "verified_claims.json"), encoding="utf-8"))
    check("e2e: c1 verified", any(r["claim_id"] == "c1" and r["status"] == "verified" for r in out))


if __name__ == "__main__":
    test_verified_two_independent_clusters()
    test_same_cluster_not_verified()
    test_ab_contradiction_refuted()
    test_anchor_failed_entails_drops_to_neutral()
    test_cite_write_non_high_risk()
    test_compound_fail_closed()
    test_binding_snapshot_hash_mismatch_exit2()
    test_binding_grade_copy_disagree_exit2()
    test_missing_verdict_unresolved_missing()
    test_m2_panel_entails_keeps_verified()
    test_m2_panel_quarantines_quotemine()
    test_m2_no_consensus_quarantines()
    test_full_chain_snapshot_classify_gate_validate()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
