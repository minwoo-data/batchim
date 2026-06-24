#!/usr/bin/env python3
"""manifest.py — 받침 signed manifest (PRD §6.5 FR-S1; M1b durability).

The manifest is the **input-closure of `validate_ledger`**: a hash of every input
(+ outputs, code versions, enabled producers, config) so a pass is reproducible
and **corruption-/skip-evident**. "Signed" = sha256 over the canonical manifest —
this is NOT cryptographic, author-tamper-proof signing (NG5); it detects accidental
mutation, torn writes, and pipeline-skip, not a motivated author holding the key.

run_id is **content-addressed** (derived from the signature) so it is reproducible
without a wall-clock (determinism, NFR-3): same closure ⇒ same run_id + signature.

verify() recomputes from disk and reports drift — for FR-S2 replay / FR-X1 exit 2.
"""

import hashlib
import json
import os

MANIFEST_VERSION = 1


# --- hashing ----------------------------------------------------------------
def file_hash(path):
    """sha256 of a file's bytes, or None if absent (an absent input is recorded
    as null so a later appearance is detectable)."""
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sign(manifest):
    """sha256 over the canonical manifest body, excluding the derived/lifecycle
    fields `signature`, `run_id` (derived FROM the signature), and `superseded_by`
    (a post-hoc annotation set when a later run supersedes this one — FR-S4 — so
    marking it must not invalidate the content signature)."""
    body = {k: v for k, v in manifest.items() if k not in ("signature", "run_id", "superseded_by")}
    return "sha256:" + hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()


# --- code versions (import siblings; NOT validate_ledger → no import cycle) --
def collect_code_versions(validate_version=None):
    import classify_risk, dedup, snapshot, entail_gate, panel, decide  # noqa: E402
    return {
        "classify_risk": classify_risk.CLASSIFIER_VERSION,
        "dedup": dedup.DEDUP_VERSION,
        "snapshot": snapshot.SNAPSHOT_VERSION,
        "entail_gate": entail_gate.GATE_VERSION,
        "panel": panel.PANEL_VERSION,
        "decision_table": decide.DECISION_TABLE_VERSION,
        "validate_ledger": validate_version,
    }


# --- build ------------------------------------------------------------------
def _read_jsonl(path):
    rows = []
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def build_manifest(session, enabled_producers, code_versions, config=None):
    """Assemble (and sign) the manifest from the on-disk closure. Pure given the
    files; returns the manifest dict with `run_id` + `signature` set."""
    art = os.path.join(session, "artifacts")
    src = os.path.join(session, "sources", "sources.jsonl")
    out = os.path.join(session, "outputs")
    fp = lambda *p: os.path.join(art, *p)

    sources = _read_jsonl(src)
    snapshots = sorted(
        ({"source_id": s.get("id"), "snapshot_path": s.get("snapshot_path"),
          "snapshot_hash": s.get("content_hash")} for s in sources),
        key=lambda r: r["source_id"] or "")

    risk = _read_jsonl(fp("risk_classifications.jsonl"))
    gaz = next((r.get("gazetteer_hash") for r in risk if r.get("gazetteer_hash")), None)
    verdicts = _read_jsonl(fp("entailment_verdicts.jsonl"))
    prompt_hashes = sorted({v.get("verifier_prompt_hash") for v in verdicts if v.get("verifier_prompt_hash")})
    model_ids = sorted({v.get("model_id") for v in verdicts if v.get("model_id")})

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "enabled_producers": sorted(enabled_producers),
        "superseded_by": None,
        "input_hashes": {
            "claim_ledger": file_hash(fp("claim_ledger.jsonl")),
            "claim_evidence_refs": file_hash(fp("claim_evidence_refs.jsonl")),
            "sources": file_hash(src),
            "snapshots": snapshots,
            "independence_partition": file_hash(fp("independence_partition.json")),
            "risk_classifications": file_hash(fp("risk_classifications.jsonl")),
            "gazetteer": gaz,
            "entailment_verdicts": file_hash(fp("entailment_verdicts.jsonl")),
            "panel_consensus": file_hash(fp("panel_consensus.jsonl")),
            "resolved_config": config,
            "verifier_prompt_hashes": prompt_hashes,
            "model_ids": model_ids,
        },
        "output_hashes": {
            "verified_claims": file_hash(os.path.join(out, "verified_claims.json")),
            "unresolved_claims": file_hash(os.path.join(out, "unresolved_claims.json")),
            "refuted_claims": file_hash(os.path.join(out, "refuted_claims.json")),
        },
        "code_versions": code_versions,
    }
    sig = sign(manifest)
    manifest["run_id"] = "run_" + sig.split(":")[1][:12]
    manifest["signature"] = sig
    return manifest


# --- write / verify ---------------------------------------------------------
def write_manifest(session, manifest):
    out = os.path.join(session, "outputs")
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "manifest.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)
    return path


def verify(session, enabled_producers, code_versions, config=None):
    """Recompute the manifest from disk and compare to the stored one.
    Returns (ok, diffs): ok=False with the list of drifted keys ⇒ tamper / skip /
    torn write (caller maps to exit 2). Also checks the stored manifest's own
    signature is internally consistent."""
    path = os.path.join(session, "outputs", "manifest.json")
    if not os.path.isfile(path):
        return False, ["manifest.json absent (gate not signed / skipped)"]
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)

    diffs = []
    if stored.get("signature") != sign(stored):
        diffs.append("signature does not match manifest body (tampered)")

    fresh = build_manifest(session, enabled_producers, code_versions, config)
    for section in ("input_hashes", "output_hashes", "code_versions"):
        s, fr = stored.get(section, {}), fresh.get(section, {})
        for k in sorted(set(s) | set(fr)):
            if s.get(k) != fr.get(k):
                diffs.append(f"{section}.{k} drift")
    return (not diffs), diffs
