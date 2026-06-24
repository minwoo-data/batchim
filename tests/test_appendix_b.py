#!/usr/bin/env python3
"""Appendix B span-match normalization acceptance corpus (PRD Appendix B, D5).
The fixture `tests/fixtures/appendix_b.jsonl` is the acceptance test that
distinguishes a normalization bug from a genuine fabrication/paraphrase. Each case
asserts span_match's verdict AND the FR-A5 re-extraction invariant: the stored
coordinates re-extract to exactly the normalized span.
Run: python tests/test_appendix_b.py"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import anchors  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "appendix_b.jsonl")
    cases = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    check("corpus loaded (>=20 cases)", len(cases) >= 20)

    for c in cases:
        name, snap, span, want = c["name"], c["snapshot"], c["span"], c["expect_match"]
        matched, start, end, occ = anchors.span_match(span, snap)
        check(f"[{name}] match == {want}", matched == want)
        if want:
            # FR-A5: coordinates re-extract to exactly the normalized span
            norm_snap = anchors.normalize(snap)
            norm_span = anchors.normalize(span)
            check(f"[{name}] re-extraction == normalized span (FR-A5)",
                  norm_snap[start:end] == norm_span)
            if "occurrence" in c:
                check(f"[{name}] occurrence_index == {c['occurrence']}", occ == c["occurrence"])


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
