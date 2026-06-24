#!/usr/bin/env python3
"""Tests for 받침 classify_risk.py: high-risk recall (over-classify), atomization
(safe split / subject-carry / lint-flag / no false split), gazetteer hash
stability. Runs standalone: `python tests/test_classify_risk.py`."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import classify_risk as cr  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


# --- recall fixture: every high-risk claim MUST be caught (false-low = leak) ---
HIGH = [
    "The EU AI Act banned real-time biometric identification.",
    "The EU AI Act bans all real-time remote biometric identification.",
    "The court barred the merger and restricted future deals.",
    "Revenue grew to $4.2bn in 2026.",
    "Inflation rose 8 percent.",
    "The court ruled against the merger.",
    "The deal closed on March 3, 2025.",
    "The fine was ₩500 million.",
    "Emissions decreased 12%.",
    "그 법은 실시간 생체인식을 금지했다.",
    "The company acquired its rival.",
    "The policy caused a shortage.",
]
NORMAL = [
    "The product has a friendly interface.",
    "Many people enjoy travelling in spring.",
    "The team discussed design ideas.",
]


def test_recall_over_classify():
    caught = sum(1 for t in HIGH if cr.classify_text(t)[0] == "high")
    recall = caught / len(HIGH)
    check(f"risk_recall >= 0.98 (got {recall:.2f})", recall >= 0.98)
    # normal claims need not all be normal (over-classify allowed), but obvious
    # prose with no signal should stay normal so the gate isn't all-noise
    normal_ok = sum(1 for t in NORMAL if cr.classify_text(t)[0] == "normal")
    check("plain prose stays normal (>=2/3)", normal_ok >= 2)


def test_atomize_safe_split_subject_carry():
    atoms, atomic, needs = cr.atomize(
        "The EU AI Act banned real-time biometric ID and required transparency reports.")
    check("split: not atomic", not atomic and not needs)
    check("split: 2 atoms", len(atoms) == 2)
    check("split: subject carried into 2nd atom",
          atoms[1].startswith("The EU AI Act") and "required transparency" in atoms[1])
    check("split: each atom high-risk", all(cr.classify_text(a)[0] == "high" for a in atoms))


def test_atomize_numeric_coordination():
    # two numeric assertions, one verb -> driven by risk-predication count, not verbs
    atoms, atomic, needs = cr.atomize("Revenue grew to $4.2bn in 2026 and to $5bn in 2027.")
    check("numeric-coord: split", not atomic and not needs and len(atoms) == 2)
    check("numeric-coord: each atom high-risk", all(cr.classify_text(a)[0] == "high" for a in atoms))


def test_atomize_unsafe_flags_lint():
    # >=2 high-risk parts mixed with a prose clause -> cannot cleanly split -> lint
    text = "The Act banned X and raised taxes 5% and people cheered."
    atoms, atomic, needs = cr.atomize(text)
    check("unsafe: flagged needs_atomization", needs and not atomic)
    check("unsafe: not split", atoms == [text])


def test_atomize_single_risk_clause_stays_atomic():
    # one risk clause + irrelevant prose -> atomic (only 1 risk predication)
    atoms, atomic, needs = cr.atomize("The agency fined the firm and everyone went home.")
    check("single-risk: stays atomic", atomic and not needs)


def test_atomize_no_false_split_noun_phrase():
    # single predication with a noun-phrase 'and' must NOT split
    atoms, atomic, needs = cr.atomize("Research and development spending was $2.0bn.")
    check("noun-phrase 'and': stays atomic", atomic and not needs and atoms == ["Research and development spending was $2.0bn."])


def test_atomize_normal_claim_untouched():
    atoms, atomic, needs = cr.atomize("The interface is clean and simple.")
    check("normal compound: stays atomic (no claim-verbs)", atomic and not needs)


def test_classify_claim_emits_atom_rows():
    rows = cr.classify_claim(
        {"claim_id": "clm_1", "text": "The Act banned X and required Y reporting by 2026."},
        cr._gazetteer_hash())
    parent = rows[0]
    atoms = rows[1:]
    check("emit: parent non-atomic", parent["atomic"] is False)
    check("emit: atom rows produced", len(atoms) >= 2)
    check("emit: atoms reference parent", all(a["atomized_from"] == "clm_1" for a in atoms))
    check("emit: atom ids unique", len({a['claim_id'] for a in atoms}) == len(atoms))


def test_gazetteer_hash_stable_and_prefixed():
    h1, h2 = cr._gazetteer_hash(), cr._gazetteer_hash()
    check("gaz hash: deterministic", h1 == h2)
    check("gaz hash: sha256 prefixed", h1.startswith("sha256:"))


if __name__ == "__main__":
    test_recall_over_classify()
    test_atomize_safe_split_subject_carry()
    test_atomize_numeric_coordination()
    test_atomize_unsafe_flags_lint()
    test_atomize_single_risk_clause_stays_atomic()
    test_atomize_no_false_split_noun_phrase()
    test_atomize_normal_claim_untouched()
    test_classify_claim_emits_atom_rows()
    test_gazetteer_hash_stable_and_prefixed()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
