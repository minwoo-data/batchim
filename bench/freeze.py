#!/usr/bin/env python3
"""freeze.py — 받침 benchmark pre-registration (PRD §9, FR-S1; M0 0.5).

Sign the **topic-set + threshold vector + human-label-set** hashes BEFORE any
tuning, so a later "we beat the baseline" claim cannot be the result of moving the
goalposts. Reuses the manifest sha256 signing (NG5: detects accidental/torn change
+ post-hoc edits, not a motivated author). Pure stdlib.

Inputs (under bench/): topics.json, thresholds.json (the threshold vector), and
labels/gold.jsonl (the adjudicated κ≥0.7 gold set). Writes bench/bench_manifest.json.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import manifest as mf  # noqa: E402 (reuse file_hash + sign)

BENCH_MANIFEST_VERSION = 1


def build(bench_dir, frozen_at=None):
    fp = lambda *p: os.path.join(bench_dir, *p)
    m = {
        "bench_manifest_version": BENCH_MANIFEST_VERSION,
        "frozen_at": frozen_at,                      # pass a timestamp in (no wall-clock here)
        "topic_set_hash": mf.file_hash(fp("topics.json")),
        "threshold_hash": mf.file_hash(fp("thresholds.json")),
        "label_set_hash": mf.file_hash(fp("labels", "gold.jsonl")),
    }
    m["signature"] = mf.sign(m)
    return m


def verify(bench_dir):
    path = os.path.join(bench_dir, "bench_manifest.json")
    if not os.path.isfile(path):
        return False, ["bench_manifest.json absent (benchmark not frozen)"]
    stored = json.load(open(path, encoding="utf-8"))
    diffs = []
    if stored.get("signature") != mf.sign(stored):
        diffs.append("signature mismatch (manifest tampered)")
    fresh = build(bench_dir, stored.get("frozen_at"))
    for k in ("topic_set_hash", "threshold_hash", "label_set_hash"):
        if stored.get(k) != fresh.get(k):
            diffs.append(f"{k} drift (benchmark changed after freeze)")
    return (not diffs), diffs


def main():
    p = argparse.ArgumentParser(description="받침 benchmark freeze/sign (M0 0.5)")
    p.add_argument("--bench-dir", default=os.path.dirname(__file__))
    p.add_argument("--frozen-at", help="ISO timestamp to record (optional)")
    p.add_argument("--verify", action="store_true")
    args = p.parse_args()

    if args.verify:
        ok, diffs = verify(args.bench_dir)
        print(f"freeze verify: {'OK' if ok else 'DRIFT'} {diffs}")
        raise SystemExit(0 if ok else 2)

    m = build(args.bench_dir, args.frozen_at)
    out = os.path.join(args.bench_dir, "bench_manifest.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2, sort_keys=True)
    miss = [k for k in ("topic_set_hash", "threshold_hash", "label_set_hash") if not m[k]]
    print(f"freeze: signed {m['signature'][:22]}… -> {out}"
          + (f"  (WARNING missing: {miss})" if miss else ""))


if __name__ == "__main__":
    main()
