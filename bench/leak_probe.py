#!/usr/bin/env python3
"""leak_probe.py — 받침 FALSE-ENTAIL (leak) probe (PRD §9 `leak_rate`).

The symmetric companion to `verified_recall.py`. That one drives TRUE claims and
asks "does the gate over-reject?"; this drives adversarial WRONG high-risk claims
and asks the core question of the whole project: **does a wrong claim leak to
`verified`?** It turns the informal smoke's narrative result (false-entail 1/6→0/6)
into a locked, expandable, regression-tested invariant.

Method (mirrors the recall probe): each adversarial claim is run through the SAME
production code (`anchors.anchors_ok` then `decide.decide_claim`). To make the test
maximally strong, the upstream is set ADVERSARIALLY cooperative — the verifier
`entails`, two independent A/B sources, and (for anchor strata) even the panel
`entails`. So if the claim still does NOT verify, it is the CODE that blocked it,
and we attribute to the first blocking step:

  block cause (first blocker): anchor:{span|numeric|polarity} → independence:* → panel:*

Strata & what must block them:
  - fabrication / number_swap / scale_swap / percent_swap / polarity_flip /
    version_swap → blocked DETERMINISTICALLY by a code anchor (the 받침 thesis),
    even with verifier+panel fooled.
  - quote_mine → anchors PASS (verbatim, number- & polarity-consistent); only the
    PANEL (refute lens) blocks it. A `demonstrates:panel_necessity` row repeats it
    with the panel DISABLED to show it then LEAKS — proving the panel is load-bearing
    (that row is EXPECTED to leak and is reported separately, not a headline failure).

  python bench/leak_probe.py [--fixture bench/adversarial/leak_claims.jsonl] [--json out.json]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import anchors  # noqa: E402
import decide   # noqa: E402

_AB = {"A", "B"}


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate_claim(row):
    """Run an adversarial claim through the real anchors + §6.7 decide. `leaked` is
    True iff a WRONG claim reached `verified`. On a (correct) block, attribute the
    first blocking step."""
    claim = row["claim"]
    m2 = row.get("panel") is not None
    tuples, ref_detail = [], []
    for ref in row["refs"]:
        ok, detail = anchors.anchors_ok(claim, ref["span"], ref["snapshot"])
        tuples.append({
            "normalized_verdict": ref.get("verifier", "entails"),
            "anchors_ok": ok,
            "cluster_id": ref["cluster"],
            "quality_rating": (ref.get("grade") or "").upper() or None,
            "source_id": ref["source_id"],
        })
        ref_detail.append({"source_id": ref["source_id"], "anchors_ok": ok,
                           "span_matched": detail["span_matched"],
                           "numeric_ok": detail["numeric_ok"],
                           "polarity_ok": detail["polarity_ok"]})

    rec = decide.decide_claim(row["claim_id"], tuples, m2_enabled=m2,
                              panel_consensus=row.get("panel"))
    status = rec["status"]
    leaked = status == "verified"
    return {"claim_id": row["claim_id"], "stratum": row.get("stratum"),
            "demonstrates": row.get("demonstrates"),
            "status": status, "status_reason": rec.get("status_reason"),
            "leaked": leaked,
            "blocked_by": None if leaked else _block_cause(row, tuples, ref_detail, rec),
            "refs": ref_detail, "note": row.get("note")}


def _block_cause(row, tuples, ref_detail, rec):
    """First blocking step in pipeline order: anchors → independence → panel."""
    for t, d in zip(tuples, ref_detail):
        if t["normalized_verdict"] in ("entails", "contradicts") and not t["anchors_ok"]:
            if not d["span_matched"]:
                return "anchor:span"
            if not d["numeric_ok"]:
                return "anchor:numeric"
            if not d["polarity_ok"]:
                return "anchor:polarity"
            return "anchor:unknown"
    if rec.get("status_reason") in ("ab_contradiction",):
        return "panel:refuted"
    if rec.get("status_reason") == "panel_no_consensus" or \
       (row.get("panel") is not None and row.get("panel") != "entails"):
        return "panel:" + str(row.get("panel"))
    entail_anchored = [t for t in tuples
                       if t["normalized_verdict"] == "entails" and t["anchors_ok"]]
    distinct = {t["cluster_id"] for t in entail_anchored}
    if len(distinct) < 2:
        return "independence:lt2_clusters"
    if not any((t["quality_rating"] or "") in _AB for t in entail_anchored):
        return "independence:no_ab_grade"
    return f"other:{rec.get('status_reason')}"


def summarize(records):
    head = [r for r in records if r["demonstrates"] != "panel_necessity"]
    demo = [r for r in records if r["demonstrates"] == "panel_necessity"]
    leaks = [r for r in head if r["leaked"]]
    blocked_by = {}
    for r in head:
        if not r["leaked"]:
            blocked_by[r["blocked_by"]] = blocked_by.get(r["blocked_by"], 0) + 1
    return {
        "leak_rate": round(len(leaks) / len(head), 4) if head else None,
        "leaks": [r["claim_id"] for r in leaks],
        "headline_n": len(head),
        "blocked_by_ranked": sorted(blocked_by.items(), key=lambda kv: (-kv[1], kv[0])),
        "panel_necessity_demo": [
            {"claim_id": r["claim_id"], "leaked_without_panel": r["leaked"]} for r in demo],
    }


def main():
    p = argparse.ArgumentParser(description="받침 false-entail (leak) probe")
    here = os.path.dirname(__file__)
    p.add_argument("--fixture", default=os.path.join(here, "adversarial", "leak_claims.jsonl"))
    p.add_argument("--json")
    args = p.parse_args()

    records = [evaluate_claim(r) for r in _read_jsonl(args.fixture)]
    s = summarize(records)

    print(f"leak_rate (headline) = {s['leak_rate']} ({len(s['leaks'])}/{s['headline_n']} wrong claims leaked)")
    if s["leaks"]:
        print(f"  !! LEAKS (wrong claim reached verified): {s['leaks']}")
    print("\nhow each wrong claim was blocked (ranked):")
    for cause, n in s["blocked_by_ranked"]:
        ids = [r["claim_id"] for r in records if r["blocked_by"] == cause]
        print(f"  {n:>2}  {cause:24} {ids}")
    for d in s["panel_necessity_demo"]:
        verdict = "LEAKS (as expected)" if d["leaked_without_panel"] else "did NOT leak (unexpected!)"
        print(f"\npanel-necessity demo: {d['claim_id']} with panel disabled -> {verdict}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": s, "records": records}, f, ensure_ascii=False, indent=2)
        print(f"\n-> {args.json}")

    # exit 1 if any headline wrong-claim leaked, OR the panel-necessity demo did NOT
    # leak (means the demo no longer demonstrates what it claims).
    demo_ok = all(d["leaked_without_panel"] for d in s["panel_necessity_demo"])
    return 1 if (s["leaks"] or not demo_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
