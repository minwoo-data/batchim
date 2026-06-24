#!/usr/bin/env python3
"""
classify_risk.py — 받침 deterministic high-risk classifier + claim atomization.

PRD §6.1 (FR-R0). Computes `computed_risk` from claim text using ONLY regex +
fixed gazetteers + POS rules — NO LLM, NO network calls (preserves the
"not by the LLM" guarantee and the scoped-determinism property, NFR-3).

Policy: OVER-classify (false-high is cheap; false-low is a leak). Target
`risk_recall >= 0.98` on the labeled fixture set.

Input : <session>/artifacts/claim_ledger.jsonl   (author-owned; claimed_*)
Output: <session>/artifacts/risk_classifications.jsonl  (gate-owned; computed_*)

NOTE: claim atomization (splitting compound high-risk claims so the verifier
judges a span against an ATOMIC claim) is a TODO for M1a — see PRD §6.1.
"""

import argparse
import json
import os
import re

CLASSIFIER_VERSION = "0.1.0-m1a"

# --- Deterministic high-risk signals (regex core; gazetteers TODO) ----------
_NUMBER = re.compile(r"\b\d[\d,\.]*\b")
_PERCENT = re.compile(r"\d+(\.\d+)?\s?%|\bpercent\b", re.I)
_CURRENCY = re.compile(r"[$€£¥₩]|\b(usd|eur|gbp|krw|won|dollars?|euros?)\b", re.I)
_DATE = re.compile(
    r"\b(\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|"
    r"aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)\b",
    re.I,
)
# Minimal causal/legal/financial verb gazetteer (TODO: expand + multilingual)
_CLAIM_VERBS = re.compile(
    r"\b(banned?|prohibit(ed|s)?|require[ds]?|caused?|led to|results? in|"
    r"increased?|decreased?|ruled?|legaliz(ed|es)?|mandate[ds]?|"
    r"acquired?|merged?|fined?)\b",
    re.I,
)


def classify_text(text: str):
    """Return (computed_risk, matched_rule_ids). Deterministic, no I/O."""
    rules = []
    if _NUMBER.search(text):
        rules.append("number")
    if _PERCENT.search(text):
        rules.append("percent")
    if _CURRENCY.search(text):
        rules.append("currency")
    if _DATE.search(text):
        rules.append("date")
    if _CLAIM_VERBS.search(text):
        rules.append("claim_verb")
    # High-risk if any numeric/date signal, OR a claim-verb present.
    high = bool(rules)
    return ("high" if high else "normal"), rules


def atomize(text: str):
    """TODO (M1a): split compound high-risk claims into atomic claims so a span
    must entail the WHOLE claim. For now, returns [text] (no-op) and flags
    likely-compound claims for review."""
    likely_compound = bool(re.search(r"\b(and|또한|그리고)\b", text, re.I))
    return [text], likely_compound


def main():
    p = argparse.ArgumentParser(description="받침 deterministic risk classifier")
    p.add_argument("--session", required=True, help="session folder")
    p.add_argument("--ledger")
    p.add_argument("--out")
    args = p.parse_args()
    ledger = args.ledger or os.path.join(args.session, "artifacts", "claim_ledger.jsonl")
    out = args.out or os.path.join(args.session, "artifacts", "risk_classifications.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    n = 0
    with open(ledger, encoding="utf-8") as f, open(out, "w", encoding="utf-8") as w:
        for line in f:
            line = line.strip()
            if not line:
                continue
            claim = json.loads(line)
            risk, rules = classify_text(claim.get("text", ""))
            _atoms, compound = atomize(claim.get("text", ""))
            w.write(json.dumps({
                "claim_id": claim.get("claim_id"),
                "computed_risk": risk,
                "matched_rule_ids": rules,
                "likely_compound": compound,  # M1a: surface for atomization work
                "atomized_from": None,
                "classifier_version": CLASSIFIER_VERSION,
                "gazetteer_hash": None,  # TODO: hash gazetteer data files (FR-S1)
                "schema_version": 1,
            }, ensure_ascii=False) + "\n")
            n += 1
    print(f"classify_risk: {n} claims classified -> {out}")


if __name__ == "__main__":
    main()
