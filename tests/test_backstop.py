#!/usr/bin/env python3
"""Tests for 받침 backstop.py (FR-R1 body re-classification). Run: python tests/test_backstop.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import backstop  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    verified = {"c1", "c2"}

    # high-risk sentence backed by a verified claim -> OK
    ok = backstop.body_backstop(
        [{"text": "Revenue rose to $4.2bn in 2026.", "claim_id": "c1"}], verified)
    check("backed high-risk -> no violation", ok == [])

    # high-risk sentence with NO claim_id -> violation
    v = backstop.body_backstop(
        [{"text": "The court banned the merger.", "claim_id": None}], verified)
    check("unbacked high-risk (no claim) -> violation", len(v) == 1 and "no claim" in v[0]["reason"])

    # high-risk sentence mapping to a NON-verified claim -> violation
    v = backstop.body_backstop(
        [{"text": "Inflation rose 8%.", "claim_id": "c99"}], verified)
    check("high-risk -> non-verified claim -> violation", len(v) == 1 and "c99" in v[0]["reason"])

    # non-high-risk prose without a claim -> fine (cite-and-write narrative)
    ok = backstop.body_backstop(
        [{"text": "The interface is clean and pleasant.", "claim_id": None}], verified)
    check("non-high-risk prose -> no violation", ok == [])

    # mixed: only the leaked one is flagged
    v = backstop.body_backstop([
        {"text": "QUIC requires TLS 1.3.", "claim_id": "c2"},        # backed
        {"text": "Sales doubled to 500 units.", "claim_id": None},   # leak
        {"text": "It feels fast.", "claim_id": None},                # prose
    ], verified)
    check("mixed body -> exactly the leak flagged", len(v) == 1 and "500" in v[0]["text"])


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
