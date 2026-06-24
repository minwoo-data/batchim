#!/usr/bin/env python3
"""replay.py — 받침 resume / determinism (PRD §6.5 FR-S2; M1b durability).

Two resume-time guards so a re-run is cheap AND tamper-evident:

1. plan(session) — REPLAY planner for the verifier stage. For every cited
   (claim, source) ref, decide: reuse the FROZEN verdict, RE-QUERY it, or abort
   (TAMPER → exit 2). Rule (binding = claim_text_hash + snapshot_hash):
     - verdict matches both current hashes        → frozen (reuse, no LLM call)
     - claim_text_hash changed (claim re-versioned, append-only) → requery (explained)
     - snapshot_hash changed under a stable claim  → tamper (unexplained) → exit 2
     - no verdict for the ref                      → requery (new work)
   The orchestrator (SKILL.md) only spawns verifiers for `requery`.

2. check_versions(manifest) — CROSS-VERSION guard. A committed run whose signed
   `*_version`s differ from the running tool's ⇒ no silent upgrade: exit 2 with an
   explicit migration instruction.
"""

import json
import os

import manifest as mf


def _read_jsonl(path):
    rows = []
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def plan(session):
    """Classify each cited (claim, source) ref into frozen / requery / tamper.
    Returns {"frozen":[...], "requery":[...], "tamper":[{ref, reason}]}."""
    art = os.path.join(session, "artifacts")
    refs = _read_jsonl(os.path.join(art, "claim_evidence_refs.jsonl"))
    claims = {c.get("claim_id"): c for c in _read_jsonl(os.path.join(art, "claim_ledger.jsonl"))}
    sources = {s.get("id"): s for s in _read_jsonl(os.path.join(session, "sources", "sources.jsonl"))}
    verdicts = {}
    for v in _read_jsonl(os.path.join(art, "entailment_verdicts.jsonl")):
        if v.get("producer", "verifier") == "verifier":
            verdicts[(v.get("claim_id"), v.get("source_id"))] = v

    frozen, requery, tamper = [], [], []
    for r in refs:
        key = (r.get("claim_id"), r.get("source_id"))
        v = verdicts.get(key)
        if v is None:
            requery.append(key)
            continue
        cur_cth = (claims.get(key[0]) or {}).get("claim_text_hash")
        cur_sh = (sources.get(key[1]) or {}).get("content_hash")
        cth_ok = v.get("claim_text_hash") == cur_cth
        sh_ok = v.get("snapshot_hash") == cur_sh
        if cth_ok and sh_ok:
            frozen.append(key)
        elif not cth_ok:
            requery.append(key)               # claim re-versioned → stale, re-query (explained)
        else:
            tamper.append({"ref": key, "reason": "snapshot_hash changed under a stable claim"})
    return {"frozen": frozen, "requery": requery, "tamper": tamper}


def check_versions(stored_manifest, running=None):
    """Compare a committed manifest's code_versions to the running tool's.
    Returns (ok, errors). A mismatch is NOT silently upgraded (FR-S2):
    errors include an explicit migration instruction."""
    running = running or mf.collect_code_versions(_validate_version())
    stored = stored_manifest.get("code_versions", {})
    errors = []
    for comp in sorted(set(stored) | set(running)):
        if stored.get(comp) != running.get(comp):
            errors.append(
                f"{comp}: committed {stored.get(comp)!r} != running {running.get(comp)!r} — "
                f"re-run the gate with the matching tool version or migrate "
                f"(`/batchim migrate --component {comp}`); no silent upgrade")
    return (not errors), errors


def _validate_version():
    # late import to avoid the validate_ledger ↔ (manifest/commit) import graph
    import validate_ledger
    return validate_ledger.VALIDATE_VERSION
