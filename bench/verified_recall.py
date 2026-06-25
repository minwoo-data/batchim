#!/usr/bin/env python3
"""verified_recall.py — 받침 OVER-ABSTENTION probe (PRD §9 `verified_recall`).

The companion to false-entail. false-entail asks "did a WRONG claim pass?";
this asks the opposite — **does the gate reject TRUE, well-evidenced high-risk
claims?** A gate that abstains on everything has leak_rate 0 and is useless, so
`verified_recall = verified ÷ should-be-verified` is a launch metric (§9).

Method: drive a control-heavy fixture of *genuinely-true* high-risk claims (RFC /
SEC / peer-reviewed, with correct cited spans) through the SAME production code the
real gate uses — `anchors.anchors_ok` (span/numeric/polarity) then
`decide.decide_claim` (§6.7 independence + grade + panel). NO LLM, NO network:
the verifier/panel votes are supplied by the fixture as the *ideal cooperating*
upstream (a true claim's correct verifier verdict is `entails`, its panel consensus
`entails`). So any miss here is the gate's OWN over-rejection, isolated from LLM
noise — and we attribute it to the first blocking step in pipeline order.

  attribution (first blocker wins): anchor:{span|numeric|polarity}
                                  → independence:{lt2_clusters|no_ab_grade}
                                  → panel:no_consensus → other

Headline `verified_recall` is computed on the `headline=true` rows (claims whose
cited evidence is *adequate by policy* — ≥2 distinct clusters incl ≥1 A/B). Misses
there are pure bugs. `headline=false` rows are single-cause DIAGNOSTIC probes that
each isolate one policy/edge over-rejection; reported separately so they don't
contaminate the headline.

  python bench/verified_recall.py [--fixture bench/control/control_claims.jsonl] [--json out.json]
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
    """Run a fixture claim through the real anchors + §6.7 decide. Returns a record
    with status, the decide reason, and (on a miss) the attributed over-rejection
    cause = the FIRST blocking step in pipeline order."""
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
    cause = None
    if status != "verified":
        cause = _attribute(row, tuples, ref_detail, rec)
    return {"claim_id": row["claim_id"], "stratum": row.get("stratum"),
            "headline": bool(row.get("headline")), "status": status,
            "status_reason": rec.get("status_reason"),
            "independent_entails": rec.get("independent_entails", 0),
            "cause": cause, "refs": ref_detail, "note": row.get("note")}


def _attribute(row, tuples, ref_detail, rec):
    """First blocking step in pipeline order: anchors → independence → panel."""
    # 1. anchors — a verifier `entails`/`contradicts` that lost its vote to an anchor.
    for t, d in zip(tuples, ref_detail):
        if t["normalized_verdict"] in ("entails", "contradicts") and not t["anchors_ok"]:
            if not d["span_matched"]:
                return "anchor:span"
            if not d["numeric_ok"]:
                return "anchor:numeric"
            if not d["polarity_ok"]:
                return "anchor:polarity"
            return "anchor:unknown"
    # 2. independence (§6.7 step 4): need ≥2 distinct entailing clusters incl ≥1 A/B.
    entail_anchored = [t for t in tuples
                       if t["normalized_verdict"] == "entails" and t["anchors_ok"]]
    distinct = {t["cluster_id"] for t in entail_anchored}
    if len(distinct) < 2:
        return "independence:lt2_clusters"
    if not any((t["quality_rating"] or "") in _AB for t in entail_anchored):
        return "independence:no_ab_grade"
    # 3. panel quarantine.
    if rec.get("status_reason") == "panel_no_consensus" or \
       (row.get("panel") is not None and row.get("panel") != "entails"):
        return "panel:no_consensus"
    return f"other:{rec.get('status_reason')}"


def summarize(records):
    head = [r for r in records if r["headline"]]
    diag = [r for r in records if not r["headline"]]
    n_head = len(head)
    v_head = sum(1 for r in head if r["status"] == "verified")
    causes = {}
    for r in records:
        if r["status"] != "verified":
            causes[r["cause"]] = causes.get(r["cause"], 0) + 1
    ranked = sorted(causes.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "headline_verified_recall": round(v_head / n_head, 4) if n_head else None,
        "headline_verified": v_head, "headline_n": n_head,
        "headline_misses": [r["claim_id"] for r in head if r["status"] != "verified"],
        "diagnostic_n": len(diag),
        "diagnostic_verified": sum(1 for r in diag if r["status"] == "verified"),
        "over_rejection_ranked": ranked,
    }


def main():
    p = argparse.ArgumentParser(description="받침 verified_recall over-abstention probe")
    here = os.path.dirname(__file__)
    p.add_argument("--fixture", default=os.path.join(here, "control", "control_claims.jsonl"))
    p.add_argument("--json")
    args = p.parse_args()

    records = [evaluate_claim(r) for r in _read_jsonl(args.fixture)]
    summary = summarize(records)

    print(f"verified_recall (headline) = {summary['headline_verified_recall']} "
          f"({summary['headline_verified']}/{summary['headline_n']})")
    if summary["headline_misses"]:
        print(f"  headline MISSES (pure over-rejection bugs): {summary['headline_misses']}")
    print(f"diagnostic probes: {summary['diagnostic_verified']}/{summary['diagnostic_n']} "
          f"verified (each headline=false row isolates one over-rejection cause)")
    print("\nover-rejection causes (ranked, all rows):")
    for cause, n in summary["over_rejection_ranked"]:
        ids = [r["claim_id"] for r in records if r["cause"] == cause]
        print(f"  {n:>2}  {cause:28} {ids}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "records": records}, f,
                      ensure_ascii=False, indent=2)
        print(f"\n-> {args.json}")

    # exit 1 if any HEADLINE claim (adequate evidence) was over-rejected — a real bug.
    return 1 if summary["headline_misses"] else 0


if __name__ == "__main__":
    sys.exit(main())
