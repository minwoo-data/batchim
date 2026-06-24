#!/usr/bin/env python3
"""score_benchmark.py — 받침 correctness metrics vs human gold (PRD §9, M0).

The headline number is **false-entail rate**, stratified by failure-mode
(fabrication / quote-mining / number-swap). Method: take the human gold
`(claim, source)` entailment labels, run them through the SAME §6.7 decision
algorithm (`decide.py`) with the run's objective anchors / clusters / grades, to
get a per-claim **gold_status**; compare to the system's status.

  false-entail = system `verified` AND gold NOT verified   (the claim shouldn't pass)
  false-neg    = system NOT verified AND gold `verified`    (the claim should pass)

precision/recall treat gold `verified` as the positive class. Reported per stratum
with a tiny Wilson-free count (CIs come later with a real n). NOT the signed run —
needs the κ≥0.7 gold set + locked topics; this just computes the metric.

Inputs:
  --session  : a completed gate session (sources, entailment_verdicts, independence_partition, outputs)
  --gold     : gold.jsonl  rows { "claim_id","source_id","label":"entails|neutral|contradicts" }
  --strata   : json { "<claim_id>": "<failure_mode>" }  (control | fabrication | number-swap | quote-mining | ...)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import decide  # noqa: E402


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _system_status(session):
    out = os.path.join(session, "outputs")
    status = {}
    for fn in ("verified_claims", "unresolved_claims", "refuted_claims"):
        for r in json.load(open(os.path.join(out, fn + ".json"), encoding="utf-8")):
            status[r["claim_id"]] = r["status"]
    return status


def gold_status(session, gold_rows):
    """Run §6.7 on the human gold labels (objective anchors/clusters/grades from
    the run) → {claim_id: gold_status}."""
    art = os.path.join(session, "artifacts")
    sources = {s["id"]: s for s in _read_jsonl(os.path.join(session, "sources", "sources.jsonl"))}
    partition = json.load(open(os.path.join(art, "independence_partition.json"), encoding="utf-8"))
    clusters = partition.get("clusters", {})
    # objective anchors per (claim, source) come from the gate's verdicts
    anchors = {(v["claim_id"], v["source_id"]): bool(v.get("anchors_ok"))
               for v in _read_jsonl(os.path.join(art, "entailment_verdicts.jsonl"))}

    by_claim = {}
    for g in gold_rows:
        cid, sid = g["claim_id"], g["source_id"]
        src = sources.get(sid, {})
        by_claim.setdefault(cid, []).append({
            "normalized_verdict": g["label"],
            "anchors_ok": anchors.get((cid, sid), True),
            "cluster_id": clusters.get(sid, sid),
            "quality_rating": (src.get("quality_rating") or "").upper() or None,
            "source_id": sid,
        })
    return {cid: decide.decide_claim(cid, tuples)["status"] for cid, tuples in by_claim.items()}


def score(system, gold, strata):
    rows, agg = [], {}
    for cid in sorted(set(system) | set(gold)):
        sv = system.get(cid) == "verified"
        gv = gold.get(cid) == "verified"
        st = strata.get(cid, "unspecified")
        fe = sv and not gv
        fn = (not sv) and gv
        rows.append({"claim_id": cid, "stratum": st, "system": system.get(cid),
                     "gold": gold.get(cid), "false_entail": fe, "false_neg": fn})
        a = agg.setdefault(st, {"n": 0, "false_entail": 0, "false_neg": 0,
                                "tp": 0, "fp": 0, "fn": 0})
        a["n"] += 1
        a["false_entail"] += fe
        a["false_neg"] += fn
        a["tp"] += sv and gv
        a["fp"] += sv and not gv
        a["fn"] += gv and not sv

    tp = sum(a["tp"] for a in agg.values())
    fp = sum(a["fp"] for a in agg.values())
    fn = sum(a["fn"] for a in agg.values())
    overall = {
        "n": len(rows),
        "false_entail_total": sum(a["false_entail"] for a in agg.values()),
        "false_neg_total": sum(a["false_neg"] for a in agg.values()),
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
    }
    return {"by_stratum": agg, "overall": overall, "rows": rows}


def main():
    p = argparse.ArgumentParser(description="받침 §9 correctness metrics vs human gold")
    p.add_argument("--session", required=True)
    p.add_argument("--gold", required=True)
    p.add_argument("--strata", required=True)
    p.add_argument("--out")
    args = p.parse_args()

    system = _system_status(args.session)
    gold = gold_status(args.session, _read_jsonl(args.gold))
    strata = json.load(open(args.strata, encoding="utf-8"))
    rep = score(system, gold, strata)

    out = args.out or os.path.join(args.session, "outputs", "benchmark_score.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    o = rep["overall"]
    print(f"score: false-entail={o['false_entail_total']}/{o['n']} false-neg={o['false_neg_total']}/{o['n']} "
          f"precision={o['precision']} recall={o['recall']} -> {out}")
    for st, a in sorted(rep["by_stratum"].items()):
        print(f"  {st:18} n={a['n']:>2} false-entail={a['false_entail']} false-neg={a['false_neg']}")


if __name__ == "__main__":
    main()
