#!/usr/bin/env python3
"""independence_probe.py — 받침 INDEPENDENCE-partition probe (PRD §6.2 FR-I0/I1).

The third measurement probe, after `verified_recall` (over-abstention) and
`leak_probe` (false-entail). Those exercise the ANCHOR layer; this exercises the
layer `decide.py` *depends on*: the independence partition. `decide` only grants
`verified` on **≥2 distinct clusters** — so if clustering is foolable, the whole
"two independent sources agree" guarantee is hollow. Two failure directions:

  - FAKE INDEPENDENCE (security): syndicated / duplicated sources that should be ONE
    cluster stay ≥2 → a single story manufactures "independent corroboration" → a
    leak. The dangerous direction.
  - OVER-MERGE (recall): genuinely independent sources wrongly merged → a true claim
    loses its second cluster → over-abstention.

Method (no LLM, no network): run each scenario's sources through the REAL composed
chain `dedup.partition → semantic.semantic_refine → provenance.provenance_refine`
(the SKILL.md Phase 4.5 order; semantic uses its deterministic lexical-fallback
embedder). Then LINK to the gate: build a claim where every source entails (anchored,
A/B) and run `decide.decide_claim` on the resulting clusters — a collapse failure
shows up as a manufactured `verified`.

  python bench/independence_probe.py [--fixture bench/adversarial/independence_claims.jsonl] [--json out.json]
"""

import argparse
import json
import os
import sys

SP = os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts")
sys.path.insert(0, SP)
import dedup        # noqa: E402
import semantic     # noqa: E402
import provenance   # noqa: E402
import decide       # noqa: E402


def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def compose_partition(sources, embedder=None):
    """The production independence chain, in SKILL.md Phase 4.5 order."""
    clusters = dedup.partition(sources)
    clusters, _ = semantic.semantic_refine(clusters, sources, embedder=embedder)
    clusters, _ = provenance.provenance_refine(clusters, sources)
    return clusters


def _would_verify(sources, clusters):
    """Does decide grant `verified` if EVERY source entails (anchored, A/B) on these
    clusters? True ⇒ the partition admitted ≥2 distinct clusters incl ≥1 A/B."""
    tuples = [{
        "normalized_verdict": "entails", "anchors_ok": True,
        "cluster_id": clusters.get(s["id"], s["id"]),
        "quality_rating": (s.get("grade") or "A").upper(), "source_id": s["id"],
    } for s in sources]
    return decide.decide_claim("probe", tuples)["status"] == "verified"


def evaluate_scenario(scn):
    sources = scn["sources"]
    clusters = compose_partition(sources)
    n_clusters = len(set(clusters.values()))
    kind = scn["kind"]
    collapsed = n_clusters == 1
    distinct = n_clusters == len(sources)
    would_verify = _would_verify(sources, clusters)

    rec = {"scenario_id": scn["scenario_id"], "kind": kind,
           "demonstrates": scn.get("demonstrates"),
           "n_sources": len(sources), "n_clusters": n_clusters,
           "would_verify_on_these_clusters": would_verify, "note": scn.get("note")}

    if kind == "collapse":
        # PASS = collapsed to one cluster (so it cannot manufacture independence)
        rec["pass"] = collapsed
        rec["fake_independence"] = not collapsed  # the security failure
        # security consequence: a non-collapsed dup set would manufacture `verified`
        rec["manufactured_verify"] = (not collapsed) and would_verify
    else:  # separate
        rec["pass"] = distinct
        rec["over_merged"] = not distinct
        rec["genuine_verify"] = would_verify  # genuine independence should enable verify
    return rec


def evaluate_gap_with_real_embedder(scn):
    """For the demonstration row: show a REAL embedding backend (stubbed here as an
    embedder that maps the syndicated pair to identical vectors) DOES collapse it —
    proving the gap is backend quality, not a logic bug."""
    sources = scn["sources"]

    def perfect_embedder(text):
        # collapse all of this scenario's texts to one point (a perfect paraphrase
        # detector would); fixed-dim unit vector.
        v = [0.0] * semantic.DIM
        v[0] = 1.0
        return v
    clusters = compose_partition(sources, embedder=perfect_embedder)
    return len(set(clusters.values())) == 1


def summarize(records, gap_collapses_with_real_embedder):
    head = [r for r in records if r["demonstrates"] != "embedding_backend_needed"]
    demo = [r for r in records if r["demonstrates"] == "embedding_backend_needed"]
    collapse = [r for r in head if r["kind"] == "collapse"]
    separate = [r for r in head if r["kind"] == "separate"]
    fakes = [r for r in collapse if r.get("fake_independence")]
    overmerged = [r for r in separate if r.get("over_merged")]
    return {
        "fake_independence_rate": round(len(fakes) / len(collapse), 4) if collapse else None,
        "fake_independence": [r["scenario_id"] for r in fakes],
        "manufactured_verify": [r["scenario_id"] for r in collapse if r.get("manufactured_verify")],
        "over_merge_rate": round(len(overmerged) / len(separate), 4) if separate else None,
        "over_merged": [r["scenario_id"] for r in overmerged],
        "collapse_n": len(collapse), "separate_n": len(separate),
        "gap_demo": [{
            "scenario_id": r["scenario_id"],
            "fake_independence_with_fallback": r.get("fake_independence"),
            "collapses_with_real_embedder": gap_collapses_with_real_embedder.get(r["scenario_id"]),
        } for r in demo],
    }


def main():
    p = argparse.ArgumentParser(description="받침 independence-partition probe")
    here = os.path.dirname(__file__)
    p.add_argument("--fixture", default=os.path.join(here, "adversarial", "independence_claims.jsonl"))
    p.add_argument("--json")
    args = p.parse_args()

    scns = _read_jsonl(args.fixture)
    records = [evaluate_scenario(s) for s in scns]
    gap_real = {s["scenario_id"]: evaluate_gap_with_real_embedder(s)
                for s in scns if s.get("demonstrates") == "embedding_backend_needed"}
    s = summarize(records, gap_real)

    print(f"fake_independence_rate = {s['fake_independence_rate']} "
          f"({len(s['fake_independence'])}/{s['collapse_n']} dup-sets stayed >=2 clusters)")
    if s["fake_independence"]:
        print(f"  !! FAKE INDEPENDENCE: {s['fake_independence']}")
    if s["manufactured_verify"]:
        print(f"  !! MANUFACTURED verified: {s['manufactured_verify']}")
    print(f"over_merge_rate = {s['over_merge_rate']} "
          f"({len(s['over_merged'])}/{s['separate_n']} independent sets wrongly merged)")
    if s["over_merged"]:
        print(f"  !! OVER-MERGED (recall loss): {s['over_merged']}")

    print("\nper-scenario:")
    for r in records:
        tag = "demo " if r["demonstrates"] else ""
        verdict = "PASS" if r.get("pass") else "FAIL"
        print(f"  {tag}{verdict:4} {r['scenario_id']:26} {r['n_sources']}src -> {r['n_clusters']}cl")
    for g in s["gap_demo"]:
        print(f"\ngap demo: {g['scenario_id']} — fallback fakes independence="
              f"{g['fake_independence_with_fallback']}, collapses with real embedder="
              f"{g['collapses_with_real_embedder']}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": s, "records": records}, f, ensure_ascii=False, indent=2)
        print(f"\n-> {args.json}")

    # exit 1 if a deterministic dup-set leaked fake independence, OR a genuinely
    # independent set was over-merged, OR the gap demo no longer demonstrates the gap.
    demo_ok = all(g["fake_independence_with_fallback"] and g["collapses_with_real_embedder"]
                  for g in s["gap_demo"])
    bad = bool(s["fake_independence"]) or bool(s["over_merged"]) or not demo_ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
