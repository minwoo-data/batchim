#!/usr/bin/env python3
"""Tests for 받침 budget.py (FR-P2 reserve-before-dispatch). Run: python tests/test_budget.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import budget  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    b = budget.Budget(3)
    check("reserve within budget", b.reserve() and b.reserve() and b.reserve())
    check("spent == 3", b.spent() == 3 and b.remaining() == 0)
    check("over-budget reserve denied", not b.reserve())
    check("denied -> exhausted flag", b.exhausted)

    # reserve-before-dispatch: a multi-slot reserve is all-or-nothing (no partial spend)
    b2 = budget.Budget(2)
    check("can't reserve 3 of 2 (no partial)", not b2.reserve(3) and b2.remaining() == 2)
    check("can reserve 2 of 2", b2.reserve(2) and b2.remaining() == 0)

    # the over-dispatch race: with budget=1, only ONE of two 'workers' may proceed
    b3 = budget.Budget(1)
    w1, w2 = b3.reserve(), b3.reserve()
    check("budget=1 -> exactly one worker dispatches", (w1, w2) == (True, False))

    # release returns slots but never exceeds total
    b4 = budget.Budget(1)
    b4.reserve(); b4.release(); b4.release()
    check("release capped at total", b4.remaining() == 1)

    check("concurrency clamped to MAX_CONCURRENT", budget.cap_concurrency(16) == budget.MAX_CONCURRENT)
    check("concurrency floor 1", budget.cap_concurrency(0) == 1)
    check("caps present", budget.MAX_VERIFIER_CALLS == 120 and budget.MAX_SPANS_PER_CLAIM == 3)


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
