#!/usr/bin/env python3
"""kappa.py — 받침 inter-annotator agreement (PRD §8, M0 0.4).

Cohen's κ between independent, blind human labelers on the shared
`(atomic_claim, span)` units. Acceptance gate: **κ ≥ 0.7** (per pair). Also lists
the disagreement units for adjudication into the gold set. Pure stdlib, no deps.

Labeler file: bench/labels/labeler_<name>.jsonl, one row per unit:
  { "unit_id":"<claim_id>::<source_id>", "label":"entails|neutral|contradicts" }
(unit_id must be identical across labelers; label vocabulary is the 3-way set.)
"""

import argparse
import glob
import json
import os

LABELS = ("entails", "neutral", "contradicts")


def cohen_kappa(a, b):
    """a, b: equal-length lists of labels (same units, same order). Returns κ."""
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    # expected agreement by chance, from each rater's marginal distribution
    pe = 0.0
    for lab in set(a) | set(b):
        pa = a.count(lab) / n
        pb = b.count(lab) / n
        pe += pa * pb
    if pe >= 1.0:                       # both raters used a single identical label
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def _load(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[r["unit_id"]] = r["label"]
    return out


def agreement(labelers, threshold=0.7):
    """labelers: {name: {unit_id: label}}. Returns a report dict with per-pair κ,
    shared-unit counts, disagreements, and a PASS/FAIL gate on min pairwise κ."""
    names = sorted(labelers)
    pairs, disagreements = [], {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            shared = sorted(set(labelers[n1]) & set(labelers[n2]))
            a = [labelers[n1][u] for u in shared]
            b = [labelers[n2][u] for u in shared]
            k = cohen_kappa(a, b)
            pairs.append({"pair": [n1, n2], "n_shared": len(shared),
                          "kappa": None if k is None else round(k, 4)})
            for u in shared:
                if labelers[n1][u] != labelers[n2][u]:
                    disagreements.setdefault(u, {})[n1] = labelers[n1][u]
                    disagreements[u][n2] = labelers[n2][u]
    kappas = [p["kappa"] for p in pairs if p["kappa"] is not None]
    min_k = min(kappas) if kappas else None
    return {
        "labelers": names,
        "pairs": pairs,
        "min_kappa": min_k,
        "mean_kappa": round(sum(kappas) / len(kappas), 4) if kappas else None,
        "threshold": threshold,
        "gate": "PASS" if (min_k is not None and min_k >= threshold) else "FAIL",
        "n_disagreements": len(disagreements),
        "disagreements": disagreements,
    }


def main():
    p = argparse.ArgumentParser(description="받침 inter-annotator κ (gate ≥0.7)")
    p.add_argument("--labels-dir", default=os.path.join(os.path.dirname(__file__), "labels"))
    p.add_argument("--threshold", type=float, default=0.7)
    p.add_argument("--out")
    args = p.parse_args()

    files = sorted(glob.glob(os.path.join(args.labels_dir, "labeler_*.jsonl")))
    if len(files) < 2:
        raise SystemExit(f"need >=2 labeler_*.jsonl files in {args.labels_dir} (found {len(files)})")
    labelers = {os.path.basename(f)[len("labeler_"):-len(".jsonl")]: _load(f) for f in files}
    rep = agreement(labelers, args.threshold)
    out = args.out or os.path.join(args.labels_dir, "kappa_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"kappa: min={rep['min_kappa']} mean={rep['mean_kappa']} gate={rep['gate']} "
          f"({rep['n_disagreements']} disagreements) -> {out}")
    raise SystemExit(0 if rep["gate"] == "PASS" else 1)


if __name__ == "__main__":
    main()
