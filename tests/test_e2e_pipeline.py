#!/usr/bin/env python3
"""test_e2e_pipeline.py — 받침 deterministic END-TO-END pipeline test.

The component probes (verified_recall / leak_probe / independence_probe) and unit
tests exercise stages in isolation. This runs the REAL M1 verification spine
end-to-end as separate processes, in the SKILL.md Phase 4.5 order:

  dedup.py → snapshot.py → entail_gate.py → panel.py → validate_ledger.py

on one synthetic session, then asserts the final `outputs/verified_claims.json`. It
locks the cross-stage DATA FLOW the prose orchestration relies on — binding integrity
(snapshot_hash/claim_text_hash/grade copies line up across stages), the anchor verdict
surviving the join, the panel gate, and the SOLE-joiner invariant (synthesis trusts
only verified_claims.json). The LLM-produced inputs (raw verifier verdicts, raw panel
votes) are supplied synthetically — no LLM, no network — so the run is reproducible.

risk_classifications is pre-written (classify_risk has its own test); semantic/
provenance are M3 refinements covered by independence_probe + their unit tests.

Run: python tests/test_e2e_pipeline.py
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts")

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def _sh(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# --- synthetic session ------------------------------------------------------
SOURCES = [
    {"id": "s_rfc", "url": "https://rfc-editor.org/rfc/rfc9114", "quality_rating": "A",
     "text": "HTTP/3 is a mapping of HTTP semantics over the QUIC transport protocol, distinct from HTTP/2 over TCP."},
    {"id": "s_blog", "url": "https://blog.example.dev/http3", "quality_rating": "B",
     "text": "Independent analysis notes that HTTP/3 carries request and response semantics over QUIC streams."},
    {"id": "s_eu_a", "url": "https://eur-lex.europa.eu/ai-act/art5", "quality_rating": "A",
     "text": "Article 5(1)(h): real-time remote biometric identification in publicly accessible spaces is prohibited, except for specified law-enforcement objectives."},
    {"id": "s_eu_b", "url": "https://summary.example.org/ai-act", "quality_rating": "B",
     "text": "Summary: such identification in publicly accessible spaces is prohibited under the Act."},
    {"id": "s_fab", "url": "https://comment.example.com/ai", "quality_rating": "A",
     "text": "Article 5 restricts certain biometric uses but carries several law-enforcement exceptions."},
]

CLAIMS = [
    {"claim_id": "c_verified", "text": "HTTP/3 maps HTTP semantics over the QUIC transport protocol."},
    {"claim_id": "c_fab", "text": "The EU AI Act bans all facial recognition with no exceptions."},
    {"claim_id": "c_qmine", "text": "The EU AI Act prohibits real-time remote biometric identification in public spaces."},
    {"claim_id": "c_normal", "text": "HTTP/3 is increasingly popular among developers."},
]

RISK = [
    {"claim_id": "c_verified", "computed_risk": "high", "atomic": True, "atomized_from": None},
    {"claim_id": "c_fab", "computed_risk": "high", "atomic": True, "atomized_from": None},
    {"claim_id": "c_qmine", "computed_risk": "high", "atomic": True, "atomized_from": None},
    {"claim_id": "c_normal", "computed_risk": "normal", "atomic": True, "atomized_from": None},
]


def _verdict(cid, sid, label, span):
    return {"claim_id": cid, "source_id": sid, "label": label, "evidence_span": span,
            "span_state": "done", "fail_reason": None, "model_id": "test-model",
            "verifier_prompt_hash": "sha256:deadbeef"}


RAW_VERDICTS = [
    # c_verified: both sources entail with verbatim spans -> anchors pass, 2 clusters
    _verdict("c_verified", "s_rfc", "entails", "HTTP/3 is a mapping of HTTP semantics over the QUIC transport protocol"),
    _verdict("c_verified", "s_blog", "entails", "HTTP/3 carries request and response semantics over QUIC streams"),
    # c_fab: fabricated span (not present in snapshot) -> span_match fails -> anchors fail
    _verdict("c_fab", "s_fab", "entails", "a total ban on facial recognition with no exceptions"),
    # c_qmine: verbatim spans (anchors PASS), 2 clusters -> verified-candidate (panel decides)
    _verdict("c_qmine", "s_eu_a", "entails", "real-time remote biometric identification in publicly accessible spaces is prohibited"),
    _verdict("c_qmine", "s_eu_b", "entails", "such identification in publicly accessible spaces is prohibited"),
]


def _vote(cid, lens, vote):
    return {"claim_id": cid, "lens": lens, "vote": vote, "vote_state": "done",
            "rationale": "test", "model_id": "test-model", "panel_prompt_hash": "sha256:cafe"}


RAW_PANEL = [
    # c_verified: 3 lenses entail -> consensus entails -> verified
    _vote("c_verified", "refute", "entails"),
    _vote("c_verified", "source_quality", "entails"),
    _vote("c_verified", "numeric_consistency", "entails"),
    # c_qmine: refute + numeric catch the dropped Art 5 exceptions -> 2 contradicts -> quarantine
    _vote("c_qmine", "refute", "contradicts"),
    _vote("c_qmine", "source_quality", "neutral"),
    _vote("c_qmine", "numeric_consistency", "contradicts"),
]


def build_session(d):
    _write_jsonl(os.path.join(d, "sources", "sources.jsonl"), SOURCES)
    ledger = [{**c, "claim_text_hash": _sh(c["text"])} for c in CLAIMS]
    _write_jsonl(os.path.join(d, "artifacts", "claim_ledger.jsonl"), ledger)
    _write_jsonl(os.path.join(d, "artifacts", "risk_classifications.jsonl"), RISK)
    _write_jsonl(os.path.join(d, "artifacts", "raw_verdicts.jsonl"), RAW_VERDICTS)
    _write_jsonl(os.path.join(d, "artifacts", "raw_panel_votes.jsonl"), RAW_PANEL)


def run_stage(script, session):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), "--session", session],
                          capture_output=True, text=True)


def run():
    d = tempfile.mkdtemp(prefix="batchim_e2e_")
    try:
        build_session(d)

        # SKILL.md Phase 4.5 order (M1 spine). dedup before snapshot (snapshot drops inline text).
        r_dedup = run_stage("dedup.py", d)
        check("dedup exit 0", r_dedup.returncode == 0)
        r_snap = run_stage("snapshot.py", d)
        check("snapshot exit 0", r_snap.returncode == 0)
        r_gate = run_stage("entail_gate.py", d)
        check(f"entail_gate exit 0 (no binding error)\n{r_gate.stdout}{r_gate.stderr}", r_gate.returncode == 0)
        r_panel = run_stage("panel.py", d)
        check("panel exit 0", r_panel.returncode == 0)
        r_val = run_stage("validate_ledger.py", d)
        # exit 0 = at least one verified high-risk claim (c_verified)
        check(f"validate_ledger exit 0\n{r_val.stdout}{r_val.stderr}", r_val.returncode == 0)

        out = os.path.join(d, "outputs")
        verified = json.load(open(os.path.join(out, "verified_claims.json"), encoding="utf-8"))
        unresolved = json.load(open(os.path.join(out, "unresolved_claims.json"), encoding="utf-8"))
        by_id = {r["claim_id"]: r for r in verified + unresolved}

        # 1) happy path: 2 independent A/B + verbatim spans + panel entails -> verified
        check("c_verified -> verified", by_id.get("c_verified", {}).get("status") == "verified")
        check("c_verified is high-risk", by_id.get("c_verified", {}).get("high_risk") is True)

        # 2) fabrication blocked deterministically (span not in snapshot) -> not verified
        check("c_fab NOT verified (anchor:span)", by_id.get("c_fab", {}).get("status") != "verified")

        # 3) quote-mine blocked by the panel (anchors passed) -> not verified
        check("c_qmine NOT verified (panel quarantine)", by_id.get("c_qmine", {}).get("status") != "verified")
        check("c_qmine reason = panel_no_consensus",
              by_id.get("c_qmine", {}).get("status_reason") == "panel_no_consensus")

        # 4) non-high-risk -> cite_write
        check("c_normal -> cite_write", by_id.get("c_normal", {}).get("status") == "cite_write")

        # 5) SOLE-joiner / no leak: only c_verified is a verified high-risk claim in the allowlist
        verified_high = [r["claim_id"] for r in verified
                         if r.get("high_risk") and r.get("status") == "verified"]
        check("exactly one verified high-risk claim (no leak)", verified_high == ["c_verified"])

        # 6) the run committed (manifest + CURRENT) — durability wiring intact
        check("CURRENT pointer written", os.path.isfile(os.path.join(d, "runs", "CURRENT"))
              or os.path.isfile(os.path.join(d, "CURRENT")))
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
