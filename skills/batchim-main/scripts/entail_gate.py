#!/usr/bin/env python3
"""entail_gate.py — 받침 isolated-verifier entailment gate (PRD §6.3, App B, FR-E1..E4).

Data-flow lock: the *verdict* (entails|neutral|contradicts) is produced by a FRESH
isolated subagent given only (atomic_claim, span+context, source_text), orchestrated
by SKILL.md. This script does the **code-enforced** half: it joins those raw verdicts
to the frozen snapshots and applies the mechanical anchors (Appendix B) —
  anchors_ok := span_matched AND numeric_ok
— then persists gate-owned `entailment_verdicts.jsonl`, each row bound to
`claim_text_hash + snapshot_hash + verifier_prompt_hash + model_id` (FR-S1).

Inputs (<session>/artifacts unless noted):
  claim_ledger.jsonl          author-owned: claim_id, text, claim_text_hash
  risk_classifications.jsonl  gate-owned : claim_id, computed_risk  (gate only high-risk)
  raw_verdicts.jsonl          verifier subagent output (contract below)
  <session>/sources/sources.jsonl  source_id → snapshot_path, content_hash, quality_rating

raw_verdicts.jsonl row (the verifier subagent's structured output — one per cited
(claim_id, source_id) pair, FR-E1):
  { "claim_id","source_id","label":"entails|neutral|contradicts",
    "evidence_span":"<verbatim quote it relied on>",
    "span_state":"done|failed","fail_reason":null,
    "model_id":"…","verifier_prompt_hash":"sha256:…" }

Output: <session>/artifacts/entailment_verdicts.jsonl  (producer="verifier").
Anchors apply symmetrically to entails and contradicts (FR-E2). A failed/malformed
verdict is recorded (never dropped) so coverage stays accounted (FR-E4).
"""

import argparse
import hashlib
import json
import os

import anchors
import snapshot as snap

GATE_VERSION = "0.1.0-m1a"
_LABELS = {"entails", "neutral", "contradicts"}


# --- pure core (no I/O) -----------------------------------------------------
def verdict_id(claim_id, source_id, producer, model_id, prompt_hash, span):
    """Deterministic, collision-resistant id (stable across replays; no RNG)."""
    key = "|".join([claim_id or "", source_id or "", producer or "",
                    model_id or "", prompt_hash or "", span or ""])
    return "v_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def build_verdict(claim, source, raw, snapshot_text):
    """Join one raw verifier verdict to its frozen snapshot + apply anchors.
    Pure: returns an entailment_verdicts.jsonl row (Appendix A). `claim` carries
    text + claim_text_hash; `source` carries content_hash + quality_rating."""
    claim_id = claim.get("claim_id")
    source_id = source.get("id")
    label = raw.get("label")
    span = raw.get("evidence_span") or ""
    span_state = raw.get("span_state") or "done"
    fail_reason = raw.get("fail_reason")
    model_id = raw.get("model_id")
    prompt_hash = raw.get("verifier_prompt_hash")

    # Unknown label enum (FR-A4): fail-closed + recorded, not exit 2.
    validation_error = None
    if label not in _LABELS:
        validation_error = f"unknown label enum: {label!r}"
        span_state, fail_reason = "failed", "malformed_label"

    # Anchors only run on a completed span; failed/malformed cannot be anchored.
    if span_state == "done":
        ok, detail = anchors.anchors_ok(claim.get("text", ""), span, snapshot_text)
    else:
        ok, detail = False, {"span_matched": False, "numeric_ok": False,
                             "span_char_start": -1, "span_char_end": -1,
                             "occurrence_index": -1}

    return {
        "verdict_id": verdict_id(claim_id, source_id, "verifier", model_id, prompt_hash, span),
        "claim_id": claim_id,
        "source_id": source_id,
        "producer": "verifier",
        "panel_round": None, "lens": None, "vote": None, "supersedes_verdict_id": None,
        "label": label,
        "span_state": span_state,
        "fail_reason": fail_reason,
        "evidence_span": span,
        "span_char_start": detail["span_char_start"],
        "span_char_end": detail["span_char_end"],
        "occurrence_index": detail["occurrence_index"],
        "span_matched": detail["span_matched"],
        "numeric_ok": detail["numeric_ok"],
        "referent_flags": detail.get("referent_flags", []),  # advisory → panel numeric lens
        "anchors_ok": ok,
        "source_grade": (source.get("quality_rating") or "").upper() or None,
        "claim_text_hash": claim.get("claim_text_hash"),
        "snapshot_hash": source.get("content_hash"),
        "verifier_prompt_hash": prompt_hash,
        "model_id": model_id,
        "gate_version": GATE_VERSION,
        "validation_error": validation_error,
        "schema_version": 1,
    }


# --- I/O --------------------------------------------------------------------
def _read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_snapshot(session, source):
    """Load the frozen snapshot text and verify it still hashes to the source's
    content_hash (binding integrity, FR-A5). Returns (text, error)."""
    rel = source.get("snapshot_path")
    if not rel:
        return None, f"source '{source.get('id')}': no snapshot_path (run snapshot.py first)"
    path = rel if os.path.isabs(rel) else os.path.join(session, rel)
    if not os.path.isfile(path):
        return None, f"source '{source.get('id')}': snapshot file missing: {rel}"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    expect = source.get("content_hash")
    if expect and snap.content_hash(text) != expect:
        return None, f"source '{source.get('id')}': snapshot hash mismatch (tampered/stale)"
    return text, None


def run(session, raw_path=None, out_path=None):
    """Join raw verifier verdicts → anchors → entailment_verdicts.jsonl.
    Returns (verdicts, errors). High-risk claims only (FR-E1)."""
    art = os.path.join(session, "artifacts")
    raw_path = raw_path or os.path.join(art, "raw_verdicts.jsonl")
    out_path = out_path or os.path.join(art, "entailment_verdicts.jsonl")

    claims = {c.get("claim_id"): c for c in _read_jsonl(os.path.join(art, "claim_ledger.jsonl"))}
    risk = {r.get("claim_id"): r for r in _read_jsonl(os.path.join(art, "risk_classifications.jsonl"))}
    sources = {s.get("id"): s for s in _read_jsonl(os.path.join(session, "sources", "sources.jsonl"))}

    high_risk = {cid for cid, r in risk.items() if r.get("computed_risk") == "high"}
    snap_cache = {}
    verdicts, errors = [], []

    for raw in _read_jsonl(raw_path):
        cid, sid = raw.get("claim_id"), raw.get("source_id")
        if cid not in high_risk:
            continue  # gate only high-risk atomic claims
        claim = claims.get(cid)
        source = sources.get(sid)
        if claim is None:
            errors.append(f"raw verdict references unknown claim_id '{cid}'")
            continue
        if source is None:
            errors.append(f"raw verdict references unknown source_id '{sid}'")
            continue
        if sid not in snap_cache:
            text, err = _load_snapshot(session, source)
            if err:
                errors.append(err)
                snap_cache[sid] = None
            else:
                snap_cache[sid] = text
        snapshot_text = snap_cache[sid]
        if snapshot_text is None:
            continue  # snapshot unavailable: binding error already recorded
        verdicts.append(build_verdict(claim, source, raw, snapshot_text))

    return verdicts, errors


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser(description="받침 entailment gate (anchors + persist)")
    p.add_argument("--session", required=True)
    p.add_argument("--raw", help="raw_verdicts.jsonl (override)")
    p.add_argument("--out", help="entailment_verdicts.jsonl (override)")
    args = p.parse_args()

    verdicts, errors = run(args.session, args.raw, args.out)
    # Binding failures (unknown id / snapshot hash mismatch) are structural (exit 2).
    if errors:
        for e in errors:
            print(f"entail_gate: ERROR {e}")
        raise SystemExit(2)

    out = args.out or os.path.join(args.session, "artifacts", "entailment_verdicts.jsonl")
    _write_jsonl(out, verdicts)
    anchored = sum(1 for v in verdicts if v["anchors_ok"])
    print(f"entail_gate: {len(verdicts)} verdicts ({anchored} anchored) -> {out}")


if __name__ == "__main__":
    main()
