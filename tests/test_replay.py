#!/usr/bin/env python3
"""Tests for 받침 replay.py (FR-S2): frozen/requery/tamper planning + cross-version
guard. Run: python tests/test_replay.py"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import replay              # noqa: E402
import manifest as mf      # noqa: E402
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
    d = tempfile.mkdtemp(prefix="batchim_replay_")
    art = os.path.join(d, "artifacts"); os.makedirs(art)
    os.makedirs(os.path.join(d, "sources"))

    def wl(p, rows):
        with open(p, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # sources: s2's content_hash is NEW (a frozen verdict will carry OLD → tamper)
    wl(os.path.join(d, "sources", "sources.jsonl"),
       [{"id": "s1", "content_hash": "sha256:s1"},
        {"id": "s2", "content_hash": "sha256:s2NEW"}])
    # ledger: c3 has a NEW claim_text_hash (re-versioned vs its frozen verdict's OLD)
    wl(os.path.join(art, "claim_ledger.jsonl"),
       [{"claim_id": "c1", "claim_text_hash": "sha256:c1"},
        {"claim_id": "c2", "claim_text_hash": "sha256:c2"},
        {"claim_id": "c3", "claim_text_hash": "sha256:c3NEW"},
        {"claim_id": "c4", "claim_text_hash": "sha256:c4"}])
    wl(os.path.join(art, "claim_evidence_refs.jsonl"),
       [{"claim_id": "c1", "source_id": "s1"},
        {"claim_id": "c2", "source_id": "s1"},
        {"claim_id": "c3", "source_id": "s1"},
        {"claim_id": "c4", "source_id": "s2"}])
    wl(os.path.join(art, "entailment_verdicts.jsonl"), [
        # c1/s1: hashes match -> frozen
        {"claim_id": "c1", "source_id": "s1", "producer": "verifier", "claim_text_hash": "sha256:c1", "snapshot_hash": "sha256:s1"},
        # c2/s1: NO verdict (omitted) -> requery
        # c3/s1: claim_text_hash OLD vs ledger NEW -> requery (re-versioned)
        {"claim_id": "c3", "source_id": "s1", "producer": "verifier", "claim_text_hash": "sha256:c3OLD", "snapshot_hash": "sha256:s1"},
        # c4/s2: claim hash ok, snapshot OLD vs source NEW -> tamper
        {"claim_id": "c4", "source_id": "s2", "producer": "verifier", "claim_text_hash": "sha256:c4", "snapshot_hash": "sha256:s2OLD"}])
    return d


def test_plan():
    d = _session()
    p = replay.plan(d)
    check("c1 frozen (hashes match)", ("c1", "s1") in p["frozen"])
    check("c2 requery (no verdict)", ("c2", "s1") in p["requery"])
    check("c3 requery (claim re-versioned)", ("c3", "s1") in p["requery"])
    check("c4 tamper (snapshot changed under stable claim)",
          any(t["ref"] == ("c4", "s2") for t in p["tamper"]))
    check("counts: 1 frozen, 2 requery, 1 tamper",
          len(p["frozen"]) == 1 and len(p["requery"]) == 2 and len(p["tamper"]) == 1)


def test_check_versions():
    running = mf.collect_code_versions(vl.VALIDATE_VERSION)
    ok, errs = replay.check_versions({"code_versions": running})
    check("matching versions -> ok", ok and not errs)

    drifted = dict(running); drifted["panel"] = "0.0.1-ancient"
    ok, errs = replay.check_versions({"code_versions": drifted})
    check("version drift -> not ok", not ok)
    check("error names component + migration", any("panel" in e and "migrate" in e for e in errs))


if __name__ == "__main__":
    test_plan()
    test_check_versions()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
