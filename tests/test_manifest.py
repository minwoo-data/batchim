#!/usr/bin/env python3
"""Tests for 받침 manifest.py (FR-S1): signed input-closure, content-addressed
run_id, reproducibility, and tamper/skip detection. Run: python tests/test_manifest.py"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import manifest as mf       # noqa: E402
import validate_ledger as vl  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def _signed_session():
    """Build a minimal session and run validate_ledger (writes a signed manifest)."""
    d = tempfile.mkdtemp(prefix="batchim_mf_")
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
         "span_state": "done", "anchors_ok": True, "source_grade": "A", "snapshot_hash": "sha256:s",
         "claim_text_hash": "sha256:c", "verifier_prompt_hash": "sha256:p", "model_id": "m"},
        {"verdict_id": "v2", "claim_id": "c1", "source_id": "s2", "producer": "verifier", "label": "entails",
         "span_state": "done", "anchors_ok": True, "source_grade": "B", "snapshot_hash": "sha256:t",
         "claim_text_hash": "sha256:c", "verifier_prompt_hash": "sha256:p", "model_id": "m"}])
    with open(os.path.join(art, "independence_partition.json"), "w", encoding="utf-8") as f:
        json.dump({"clusters": {"s1": "cl_a", "s2": "cl_b"}}, f)
    vl.validate(d, os.path.join(art, "claim_ledger.jsonl"),
                os.path.join(d, "sources", "sources.jsonl"), os.path.join(d, "outputs"))
    return d


def _cv():
    return mf.collect_code_versions(vl.VALIDATE_VERSION)


def run():
    d = _signed_session()
    man_path = os.path.join(d, "outputs", "manifest.json")
    check("manifest written", os.path.isfile(man_path))
    man = json.load(open(man_path, encoding="utf-8"))

    check("signature present + prefixed", str(man.get("signature", "")).startswith("sha256:"))
    check("run_id content-addressed", man["run_id"] == "run_" + man["signature"].split(":")[1][:12])
    check("enabled_producers = verifier only (no panel)", man["enabled_producers"] == ["verifier"])
    check("code_versions recorded", man["code_versions"]["validate_ledger"] == vl.VALIDATE_VERSION)
    check("snapshots ordered + hashed", [s["source_id"] for s in man["input_hashes"]["snapshots"]] == ["s1", "s2"])
    check("output hashed", str(man["output_hashes"]["verified_claims"]).startswith("sha256:"))

    # reproducible: rebuilding from the same closure yields the same signature
    man2 = mf.build_manifest(d, ["verifier"], _cv())
    check("reproducible signature", man2["signature"] == man["signature"])
    check("reproducible run_id", man2["run_id"] == man["run_id"])

    # verify: clean session passes
    ok, diffs = mf.verify(d, ["verifier"], _cv())
    check("verify clean -> ok", ok and not diffs)

    # tamper: mutate an input artifact -> verify detects drift
    with open(os.path.join(d, "artifacts", "claim_ledger.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"claim_id": "c2", "text": "y", "claim_text_hash": "sha256:c2"}) + "\n")
    ok, diffs = mf.verify(d, ["verifier"], _cv())
    check("verify tampered input -> not ok", not ok and any("claim_ledger" in x for x in diffs))

    # tamper: edit the stored manifest body -> internal signature mismatch
    man["enabled_producers"] = ["verifier", "panel"]
    json.dump(man, open(man_path, "w", encoding="utf-8"))
    ok, diffs = mf.verify(d, ["verifier"], _cv())
    check("verify tampered manifest -> signature mismatch", not ok and any("signature" in x for x in diffs))

    # skip: no manifest at all
    d2 = tempfile.mkdtemp(prefix="batchim_mf2_"); os.makedirs(os.path.join(d2, "outputs"))
    ok, diffs = mf.verify(d2, ["verifier"], _cv())
    check("verify missing manifest -> not ok (skip)", not ok)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
