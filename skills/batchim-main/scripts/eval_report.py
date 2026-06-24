#!/usr/bin/env python3
"""
eval_report.py — 받침 **Phase-7 평가 채점기 / 하드게이트** (PRD §9, FR-X2).

검증 게이트가 실제로 지켜졌는지 코드로 계측한다(LLM judge 없음 → 재현·A/B 가능).
**새 스키마 정합:** 결정 레코드(`verified_claims.json` 등)는 status만 담고 claim 텍스트는
`artifacts/claim_ledger.jsonl`에 있으므로 claim_id로 조인해 본문 매칭을 한다. 또한
high-risk `verified`와 비-high-risk `cite_write`를 구분한다.

구조 지표(게이트 강제):
  - citation_resolution_rate  본문 인용 src_xxx 중 레지스트리 존재 비율 (깨진 인용 = 환각)
  - missing_entailment_proof_rate  high-risk verified 주장 중 anchored-entails 증명이 빠진 비율 (FR-X2 → 0이어야)
  - span_match_rate            verified 증명 verdict의 verbatim-span 일치 비율 (100%여야)
  - coverage_ok               모든 high-risk 주장이 terminal status를 가짐 (FR-X3 백스톱)
정직성 지표:
  - leak_rate                 unresolved/refuted 주장이 본문에 단정형으로 샌 비율 (verified-only 게이트)
  - verified_coverage_rate    high-risk verified 주장이 본문에 실제 등장한 비율
  - orphan_source_rate        레지스트리에 있으나 미인용 소스 비율
  - degraded_verdict_rate     failed/malformed로 마감된 verdict 비율 (NFR-1)
무결성 게이트:
  - manifest_ok               서명 매니페스트가 있고 CURRENT run이 superseded 아님 (FR-X1/S4)

verdict FAIL(exit 2 — 마감 금지) 조건: leak 또는 dangling 또는
missing_entailment_proof_rate>0 또는 citation_resolution<100% 또는 coverage 실패
또는 manifest 미서명/superseded.
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import commit as cm  # noqa: E402

SRC_TOKEN = re.compile(r"src_[0-9a-zA-Z_]+")
NGRAM = 6


def _read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return out


def _read_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default if default is not None else []


def _load_body(out_dir):
    parts = []
    for p in sorted(glob.glob(os.path.join(out_dir, "**", "*.md"), recursive=True)):
        with open(p, encoding="utf-8") as f:
            parts.append(f.read())
    return "\n".join(parts)


def _content(s):
    return re.sub(r"[^0-9A-Za-z가-힣%]", "", s or "")


def _ngrams(s, n=NGRAM):
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else set()


def _present(text, cid, body_blob, body_raw, exclude_blob=""):
    if cid and cid in body_raw:
        return True
    grams = _ngrams(_content(text)) - _ngrams(exclude_blob)
    return any(g in body_blob for g in grams)


def evaluate(session, out_dir=None, sources_path=None):
    out_dir = out_dir or os.path.join(session, "outputs")
    art = os.path.join(session, "artifacts")
    sources_path = sources_path or os.path.join(session, "sources", "sources.jsonl")

    body = _load_body(out_dir)
    body_blob = _content(body)
    source_ids = {s.get("id") for s in _read_jsonl(sources_path) if s.get("id")}

    # claim text lives in the ledger (decision records are status-only now)
    text_of = {c.get("claim_id"): c.get("text", "") for c in _read_jsonl(os.path.join(art, "claim_ledger.jsonl"))}
    risk = {r.get("claim_id"): r for r in _read_jsonl(os.path.join(art, "risk_classifications.jsonl"))
            if r.get("atomized_from") is None}
    high_risk_ids = {cid for cid, r in risk.items() if r.get("computed_risk") == "high"}
    verdicts = _read_jsonl(os.path.join(art, "entailment_verdicts.jsonl"))
    anchored_entails = {(v["claim_id"], v["source_id"])
                        for v in verdicts if v.get("label") == "entails" and v.get("anchors_ok")}

    verified_all = _read_json(os.path.join(out_dir, "verified_claims.json"))
    verified = [c for c in verified_all if c.get("high_risk") and c.get("status") == "verified"]
    unresolved = _read_json(os.path.join(out_dir, "unresolved_claims.json"))
    refuted = _read_json(os.path.join(out_dir, "refuted_claims.json"))

    # 1) citation resolution + orphans
    cited = set(SRC_TOKEN.findall(body))
    dangling = sorted(c for c in cited if c not in source_ids)
    cite_rate = (len(cited - set(dangling)) / len(cited)) if cited else 1.0
    orphans = sorted(sid for sid in source_ids if sid not in cited)
    orphan_rate = (len(orphans) / len(source_ids)) if source_ids else 0.0

    # 2) missing entailment proof (FR-X2): every verified claim's proof_source_ids
    #    must each have an anchored-entails verdict.
    missing_proof = [c["claim_id"] for c in verified
                     if not all((c["claim_id"], sid) in anchored_entails
                                for sid in (c.get("proof_source_ids") or []))]
    missing_proof_rate = (len(missing_proof) / len(verified)) if verified else 0.0

    # 3) span_match_rate over proof verdicts of verified claims
    proof_pairs = {(c["claim_id"], sid) for c in verified for sid in (c.get("proof_source_ids") or [])}
    proof_v = [v for v in verdicts if (v["claim_id"], v["source_id"]) in proof_pairs]
    span_ok = sum(1 for v in proof_v if v.get("span_matched"))
    span_match_rate = (span_ok / len(proof_v)) if proof_v else 1.0

    # 4) coverage invariant (FR-X3 backstop): every high-risk claim has a terminal status
    decided = {c["claim_id"] for c in verified_all + unresolved + refuted}
    coverage_missing = sorted(high_risk_ids - decided)
    coverage_ok = not coverage_missing

    # 5) degraded verdict rate
    degraded = sum(1 for v in verdicts if v.get("span_state") == "failed" or v.get("fail_reason"))
    degraded_rate = (degraded / len(verdicts)) if verdicts else 0.0

    # 6) leak: unresolved/refuted asserted in body (verified text = shared-context exclude)
    verified_blob = _content(" ".join(text_of.get(c["claim_id"], "") for c in verified))
    leaks = [{"claim_id": c.get("claim_id"), "status": c.get("status"),
              "text": text_of.get(c.get("claim_id"), "")}
             for c in unresolved + refuted
             if _present(text_of.get(c.get("claim_id"), ""), c.get("claim_id"), body_blob, body, verified_blob)]
    pool = len(unresolved) + len(refuted)
    leak_rate = (len(leaks) / pool) if pool else 0.0

    # 7) verified coverage (allowlist actually consumed)
    covered = sum(1 for c in verified
                  if _present(text_of.get(c["claim_id"], ""), c["claim_id"], body_blob, body))
    cov_rate = (covered / len(verified)) if verified else 1.0

    # 8) manifest integrity (FR-X1/S4): signed + CURRENT not superseded
    manifest_ok, manifest_note = True, "ok"
    cur = _read_json(os.path.join(session, "CURRENT"), default={})
    if not cur:
        manifest_ok, manifest_note = False, "no CURRENT (run not committed/signed)"
    else:
        try:
            cm.assert_publishable(session, cur["run_id"])
        except (ValueError, KeyError) as e:
            manifest_ok, manifest_note = False, str(e)

    fail = bool(leaks or dangling or missing_proof or not coverage_ok
                or cite_rate < 1.0 or not manifest_ok)
    return {
        "verdict": "FAIL" if fail else "PASS",
        "metrics": {
            "citation_resolution_rate": round(cite_rate, 3),
            "missing_entailment_proof_rate": round(missing_proof_rate, 3),
            "span_match_rate": round(span_match_rate, 3),
            "verified_coverage_rate": round(cov_rate, 3),
            "leak_rate": round(leak_rate, 3),
            "orphan_source_rate": round(orphan_rate, 3),
            "degraded_verdict_rate": round(degraded_rate, 3),
        },
        "coverage_ok": coverage_ok,
        "manifest_ok": manifest_ok,
        "manifest_note": manifest_note,
        "counts": {
            "high_risk_verified": len(verified),
            "cite_write": sum(1 for c in verified_all if c.get("status") == "cite_write"),
            "unresolved": len(unresolved), "refuted": len(refuted),
            "citations_total": len(cited), "citations_dangling": len(dangling),
            "sources_total": len(source_ids), "orphan_sources": len(orphans),
            "leaks": len(leaks), "missing_proof": len(missing_proof),
            "coverage_missing": len(coverage_missing),
        },
        "leaks": leaks, "dangling_citations": dangling,
        "missing_proof_claims": missing_proof, "coverage_missing": coverage_missing,
    }


def _print(rep):
    m, c = rep["metrics"], rep["counts"]
    o = sys.stderr
    print("=== eval_report (§9) ===", file=o)
    print(f"  verdict: {rep['verdict']}  (manifest: {rep['manifest_note']})", file=o)
    print(f"  citation_resolution={m['citation_resolution_rate']:.0%} (dangling {c['citations_dangling']}/{c['citations_total']})", file=o)
    print(f"  missing_entailment_proof={m['missing_entailment_proof_rate']:.0%}  span_match={m['span_match_rate']:.0%}  coverage_ok={rep['coverage_ok']}", file=o)
    print(f"  leak_rate={m['leak_rate']:.0%} ({c['leaks']}/{c['unresolved']+c['refuted']})  verified_coverage={m['verified_coverage_rate']:.0%}", file=o)
    print(f"  orphan={m['orphan_source_rate']:.0%}  degraded={m['degraded_verdict_rate']:.0%}  (high-risk verified {c['high_risk_verified']}, cite_write {c['cite_write']})", file=o)
    for lk in rep["leaks"]:
        print(f"  [LEAK] {lk['claim_id']} ({lk['status']}): {lk['text'][:50]}", file=o)
    if rep["dangling_citations"]:
        print(f"  [DANGLING] {rep['dangling_citations']}", file=o)
    if rep["coverage_missing"]:
        print(f"  [COVERAGE] high-risk claims with no status: {rep['coverage_missing']}", file=o)


def main():
    p = argparse.ArgumentParser(description="받침 Phase-7 평가 채점기 (§9 하드게이트)")
    p.add_argument("--session", required=True)
    p.add_argument("--out-dir")
    p.add_argument("--sources")
    args = p.parse_args()
    rep = evaluate(args.session, args.out_dir, args.sources)
    out_dir = args.out_dir or os.path.join(args.session, "outputs")
    with open(os.path.join(out_dir, "eval_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    _print(rep)
    sys.exit(0 if rep["verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
