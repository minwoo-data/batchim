#!/usr/bin/env python3
"""backstop.py — 받침 Phase-6 body re-classification backstop (PRD §6.1 FR-R1).

Turns the *static* `risk_recall` number into a *runtime invariant*: re-run the
deterministic classifier over the RENDERED body sentences; if any body sentence
trips a high-risk rule but does not map to a `verified` claim, the run is
structurally wrong (a high-risk assertion leaked into the body without passing the
gate) ⇒ exit 2. Cheap insurance against a classifier miss or a synthesis slip.

The synthesizer annotates each body sentence with the `claim_id` it asserts (it
must — the data-flow lock says the body's high-risk claims come from
`verified_claims.json`). An unannotated or non-verified high-risk sentence fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import classify_risk  # noqa: E402


def body_backstop(sentences, verified_ids):
    """sentences: [{"text": str, "claim_id": str|None}]. verified_ids: set of
    claim_ids with status `verified`. Returns the list of violating sentences
    (high-risk text not backed by a verified claim). Empty ⇒ invariant holds."""
    verified_ids = set(verified_ids or ())
    violations = []
    for s in sentences:
        text = s.get("text", "")
        risk, rules = classify_risk.classify_text(text)
        if risk != "high":
            continue
        cid = s.get("claim_id")
        if cid not in verified_ids:
            violations.append({
                "text": text,
                "matched_rule_ids": rules,
                "claim_id": cid,
                "reason": ("unbacked high-risk body sentence: maps to "
                           + ("no claim" if not cid else f"non-verified claim '{cid}'")),
            })
    return violations


def main():
    import argparse, json
    p = argparse.ArgumentParser(description="받침 Phase-6 body backstop (FR-R1)")
    p.add_argument("--session", required=True)
    p.add_argument("--body", required=True, help="body_sentences.jsonl ({text, claim_id})")
    args = p.parse_args()

    verified = {r["claim_id"] for r in json.load(
        open(os.path.join(args.session, "outputs", "verified_claims.json"), encoding="utf-8"))
        if r.get("status") == "verified"}
    sentences = []
    with open(args.body, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sentences.append(json.loads(line))

    v = body_backstop(sentences, verified)
    if v:
        print(f"backstop: FAIL — {len(v)} unbacked high-risk body sentences (exit 2):", file=sys.stderr)
        for x in v:
            print(f"  - {x['reason']}: {x['text'][:80]}", file=sys.stderr)
        raise SystemExit(2)
    print("backstop: OK — every high-risk body sentence maps to a verified claim")


if __name__ == "__main__":
    main()
