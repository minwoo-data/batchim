#!/usr/bin/env python3
"""
classify_risk.py — 받침 deterministic high-risk classifier + claim atomization.

PRD §6.1 (FR-R0). Computes `computed_risk` from claim text using ONLY regex +
fixed gazetteers + light POS heuristics — NO LLM, NO network calls (preserves the
"not by the LLM" guarantee and the scoped-determinism property, NFR-3).

Policy: OVER-classify (false-high is cheap; false-low is a leak). Target
`risk_recall >= 0.98` on the labeled fixture set.

Atomization (FR-E1: the verifier judges a span against an ATOMIC claim):
compound high-risk claims are split into atomic sub-claims so a span must entail
the WHOLE claim — closing the conjunctive partial-entailment leak ("X and Y"
marked entailed by a span that only supports X). We split ONLY when it is safe
(each resulting atom is itself a high-risk predication); a compound we cannot
safely split is flagged `needs_atomization=true` so the ledger-write step
lint-rejects it (PRD §6.1: "atomized OR lint-rejected at ledger write"). Either
way a non-atomic high-risk claim never reaches the verifier as a single unit.

Input : <session>/artifacts/claim_ledger.jsonl       (author-owned; claimed_*)
Output: <session>/artifacts/risk_classifications.jsonl (gate-owned; computed_*)
"""

import argparse
import hashlib
import json
import os
import re

CLASSIFIER_VERSION = "0.2.0-m1a"

# --- Deterministic high-risk signals (canonical rule source; hashed below) ---
# Kept in one dict so classify + gazetteer_hash share a single source of truth.
RULES = {
    "number":   r"\b\d[\d,\.]*\b",
    "percent":  r"\d+(\.\d+)?\s?%|\bpercent\b|\b퍼센트\b",
    "currency": r"[$€£¥₩]|\b(usd|eur|gbp|krw|won|dollars?|euros?|원|달러)\b",
    "date":     (r"\b(\d{4}|\d{1,2}/\d{1,2}/\d{2,4}|"
                 r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|"
                 r"aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)\b"),
    # causal / legal / financial predicate verbs (multilingual; expand over time)
    "claim_verb": (r"\b(banned?|prohibit(ed|s)?|require[ds]?|caused?|led to|"
                   r"results? in|increased?|decreased?|reduced?|ruled?|"
                   r"legaliz(ed|es)?|mandate[ds]?|acquired?|merged?|fined?|"
                   r"approved?|rejected?|found|sued?|convicted?)\b|"
                   r"(금지|허용|의무화|인수|합병|판결|벌금|승인|기각)(했|한|함|됐|된)"),
}
_RX = {k: re.compile(v, re.I) for k, v in RULES.items()}
_CLAIM_VERB = _RX["claim_verb"]
_RISK_KEYS = ("number", "percent", "currency", "date", "claim_verb")

# Clause-level coordinators (NOT noun-phrase "and": we additionally require each
# side to be its own high-risk predication before accepting a split).
_COORD = re.compile(
    r",?\s+and\s+also\s+|,?\s+as\s+well\s+as\s+|,?\s+and\s+|;\s+|"
    r",?\s+그리고\s+|,?\s+또한\s+|\s+및\s+",
    re.I,
)


def _gazetteer_hash() -> str:
    """sha256 over the canonical rule set (+ coordinator) so the manifest can pin
    the gazetteer/rule data SEPARATELY from classifier_version (FR-R0, FR-S1)."""
    canon = json.dumps({"rules": RULES, "coord": _COORD.pattern,
                        "version": CLASSIFIER_VERSION}, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def classify_text(text: str):
    """Return (computed_risk, matched_rule_ids). Deterministic, no I/O.
    High-risk if ANY numeric/date/currency/percent signal OR a claim-verb."""
    rules = [k for k in _RISK_KEYS if _RX[k].search(text or "")]
    return ("high" if rules else "normal"), rules


def _is_predication(part: str) -> bool:
    """A fragment that is itself a high-risk predication (carries its own risk
    signal) — the bar each atom must clear for a split to be accepted."""
    risk, _ = classify_text(part)
    return risk == "high"


def atomize(text: str):
    """Split a compound HIGH-RISK claim into atomic predications.

    Returns (atoms, atomic, needs_atomization):
      - atomic=True, atoms=[text]                  → already atomic, no split
      - atomic=False, atoms=[a, b, ...]            → safely atomized (candidates)
      - atomic=False, atoms=[text], needs=True     → compound but UNSAFE to split
                                                     ⇒ lint-reject at ledger write
    Compound detection is driven by HIGH-RISK PREDICATIONS, not just claim-verbs,
    so it catches both verb-coordinated ("banned X and required Y") and
    numeric-coordinated ("grew to $4.2bn in 2026 and to $5bn in 2027") compounds
    while ignoring noun-phrase "and" ("research and development spending was $2bn"
    has only one risk part → no split). A split is accepted only if EVERY atom is
    itself high-risk; ≥2 risk parts mixed with prose ⇒ unsafe ⇒ needs_atomization.
    Conservative by design (over-flag, never silently pass a conjunctive claim)."""
    text = (text or "").strip()
    parts = [p.strip() for p in _COORD.split(text) if p and p.strip()]
    if len(parts) < 2:
        return [text], True, False

    # Carry a shared leading subject (text before the first claim-verb) into any
    # atom that begins with a verb (i.e. lost its subject to the coordinator).
    verbs = list(_CLAIM_VERB.finditer(text))
    subject = text[: verbs[0].start()].strip() if verbs else ""
    atoms = []
    for i, part in enumerate(parts):
        if i > 0 and subject and _CLAIM_VERB.match(part):
            part = f"{subject} {part}".strip()
        atoms.append(part)

    risk_parts = [a for a in atoms if _is_predication(a)]
    if len(risk_parts) < 2:
        return [text], True, False              # ≤1 risk predication ⇒ atomic
    if all(_is_predication(a) for a in atoms):
        return atoms, False, False              # every atom high-risk ⇒ safely split
    return [text], False, True                  # risk parts mixed w/ prose ⇒ lint


def classify_claim(claim, gaz_hash):
    """Build the risk_classifications.jsonl row(s) for one ledger claim. Returns a
    list (the parent row, plus advisory candidate-atom rows when safely split)."""
    cid = claim.get("claim_id")
    text = claim.get("text", "")
    risk, rules = classify_text(text)

    if risk != "high":
        atoms, atomic, needs = [text], True, False
    else:
        atoms, atomic, needs = atomize(text)

    parent = {
        "claim_id": cid,
        "computed_risk": risk,
        "matched_rule_ids": rules,
        "atomic": atomic,
        "needs_atomization": needs,        # high-risk compound the gate couldn't split
        "candidate_atoms": atoms if not atomic else None,  # advisory for ledger-write
        "atomized_from": None,
        "classifier_version": CLASSIFIER_VERSION,
        "gazetteer_hash": gaz_hash,
        "schema_version": 1,
    }
    rows = [parent]
    if not atomic and not needs:
        for j, atom in enumerate(atoms):
            ar, arules = classify_text(atom)
            rows.append({
                "claim_id": f"{cid}__a{j}",
                "computed_risk": ar,
                "matched_rule_ids": arules,
                "atomic": True,
                "needs_atomization": False,
                "candidate_atoms": None,
                "atomized_from": cid,
                "atom_text": atom,
                "classifier_version": CLASSIFIER_VERSION,
                "gazetteer_hash": gaz_hash,
                "schema_version": 1,
            })
    return rows


def main():
    p = argparse.ArgumentParser(description="받침 deterministic risk classifier")
    p.add_argument("--session", required=True, help="session folder")
    p.add_argument("--ledger")
    p.add_argument("--out")
    args = p.parse_args()
    ledger = args.ledger or os.path.join(args.session, "artifacts", "claim_ledger.jsonl")
    out = args.out or os.path.join(args.session, "artifacts", "risk_classifications.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    gaz_hash = _gazetteer_hash()
    n_claims = n_high = n_needs = n_rows = 0
    tmp = out + ".tmp"
    with open(ledger, encoding="utf-8") as f, open(tmp, "w", encoding="utf-8") as w:
        for line in f:
            line = line.strip()
            if not line:
                continue
            claim = json.loads(line)
            n_claims += 1
            for row in classify_claim(claim, gaz_hash):
                if row["atomized_from"] is None and row["computed_risk"] == "high":
                    n_high += 1
                if row.get("needs_atomization"):
                    n_needs += 1
                w.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_rows += 1
    os.replace(tmp, out)
    print(f"classify_risk: {n_claims} claims ({n_high} high-risk, "
          f"{n_needs} need atomization) -> {n_rows} rows -> {out}")


if __name__ == "__main__":
    main()
