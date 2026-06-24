#!/usr/bin/env python3
"""panel.py — 받침 N=3 verification panel (PRD §6.8 FR-P1/P3) — IN MVP.

The quote-mining defense. M1 anchors catch fabricated quotes + number swaps, but
NOT quote-mining (a real, verbatim, number-consistent quote that doesn't entail
the broader claim — the EU-AI-Act "with exceptions" case). For each high-risk
*verified-candidate* claim, three PROMPT-DIVERSE lenses cross-check it:
  - refute            : adversarially hunt for a missing qualifier / exception /
                        scope overreach that makes the claim false-as-stated.
  - source_quality    : are the cited sources adequate / primary / independent?
  - numeric_consistency: does the claim's scope/quantity exactly match the support?
Each lens is a FRESH subagent (orchestrated by SKILL.md, like the verifier) that
emits a vote ∈ {entails, neutral, contradicts}. This script does the CODE half:
2-of-3 consensus. A 1-1-1 split or any missing/failed lens ⇒ no_consensus ⇒
quarantine (the claim cannot be `verified`; §6.8). The verified gate (§6.7-4b)
requires `panel_consensus == "entails"`.

Input : <session>/artifacts/raw_panel_votes.jsonl   (lens subagent output, below)
Output: <session>/artifacts/panel_consensus.jsonl   (gate-owned; one row per claim)

raw_panel_votes.jsonl row (one per (claim_id, lens)):
  { "claim_id","lens":"refute|source_quality|numeric_consistency",
    "vote":"entails|neutral|contradicts","vote_state":"done|failed",
    "rationale":"…","model_id":"…","panel_prompt_hash":"sha256:…" }
"""

import argparse
import json
import os

PANEL_VERSION = "0.1.0-m2"
LENSES = ("refute", "source_quality", "numeric_consistency")
_LABELS = {"entails", "neutral", "contradicts"}


# --- pure consensus core (no I/O) -------------------------------------------
def consensus(votes):
    """votes: iterable of label strings (only valid/done votes). Returns the
    2-of-3 consensus label, or "no_consensus". FR-P1: requires all N=3 present
    (caller drops failed/malformed before calling); with <3 valid votes ⇒
    no_consensus; a 1-1-1 split ⇒ no_consensus."""
    votes = [v for v in votes if v in _LABELS]
    if len(votes) < 3:
        return "no_consensus"
    counts = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1
    label, n = max(counts.items(), key=lambda kv: kv[1])
    return label if n >= 2 else "no_consensus"


def panel_verdict(claim_id, lens_votes):
    """lens_votes: {lens: {"vote","vote_state",...}}. Returns a panel_consensus
    row. Missing or failed lenses are recorded and force no_consensus."""
    valid, missing, failed = {}, [], []
    for lens in LENSES:
        v = lens_votes.get(lens)
        if v is None:
            missing.append(lens)
        elif v.get("vote_state") == "failed" or v.get("vote") not in _LABELS:
            failed.append(lens)
        else:
            valid[lens] = v["vote"]
    cons = "no_consensus" if (missing or failed) else consensus(valid.values())
    return {
        "claim_id": claim_id,
        "panel_consensus": cons,
        "votes": {lens: lens_votes.get(lens, {}).get("vote") for lens in LENSES},
        "n_valid": len(valid),
        "missing_lenses": missing,
        "failed_lenses": failed,
        "panel_round": 1,
        "panel_version": PANEL_VERSION,
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


def run(session, raw_path=None, out_path=None):
    art = os.path.join(session, "artifacts")
    raw_path = raw_path or os.path.join(art, "raw_panel_votes.jsonl")
    out_path = out_path or os.path.join(art, "panel_consensus.jsonl")

    by_claim = {}
    for r in _read_jsonl(raw_path):
        by_claim.setdefault(r.get("claim_id"), {})[r.get("lens")] = r

    rows = [panel_verdict(cid, lv) for cid, lv in by_claim.items()]
    return rows, out_path


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def main():
    p = argparse.ArgumentParser(description="받침 N=3 panel (2-of-3 consensus)")
    p.add_argument("--session", required=True)
    p.add_argument("--raw")
    p.add_argument("--out")
    args = p.parse_args()
    rows, out = run(args.session, args.raw, args.out)
    _write_jsonl(args.out or out, rows)
    ent = sum(1 for r in rows if r["panel_consensus"] == "entails")
    quar = sum(1 for r in rows if r["panel_consensus"] != "entails")
    print(f"panel: {len(rows)} claims -> {ent} consensus-entails, {quar} quarantined -> {out}")


if __name__ == "__main__":
    main()
