#!/usr/bin/env python3
"""
validate_ledger.py — 받침 **SOLE joiner / decision gate** (M1a; PRD §6.7, FR-A3/A5, FR-E3).

데이터 흐름 락: 이 스크립트만이 `outputs/verified_claims.json`을 생산한다 — 합성(Phase 5)은
그 파일만 근거로 하므로 게이트를 건너뛰면 합성 입력이 없다(우회 불가).

M1a 책임 (서명/매니페스트는 M1b):
  1. join — sources + claim_ledger + risk_classifications + independence_partition
     + entailment_verdicts 를 읽어 high-risk atomic 주장마다 §6.7 튜플을 만든다.
  2. effective_verdict — (claim, source)별 1개. producer=panel이 있으면 verifier를
     supersede(FR-P3); M1a는 보통 verifier만.
  3. anchors/verdict 정규화 — span_state=failed→failed, 미지 라벨→malformed,
     anchors_ok=false entails/contradicts → decide가 neutral 처리.
  4. decide.decide_claim(§6.7) — 코드가 status를 **계산**(LLM이 못 씀).
  5. 바인딩 무결성(FR-A5): source_id 존재 / snapshot_hash==sources.content_hash /
     claim_text_hash==ledger / source_grade==sources.quality_rating → 위반은 exit 2.
  6. 커버리지 불변식(FR-X3): 모든 high-risk 주장은 status 또는 not_run_reason을 가진다.

종료 코드: 0 통과 · 1 verified 0건(정상 기권)/degraded · 2 구조적 에러.

입력(<session>): sources/sources.jsonl, artifacts/{claim_ledger, risk_classifications,
  entailment_verdicts}.jsonl, artifacts/independence_partition.json
출력(<session>/outputs): verified_claims.json (전체 결정 레코드 = 합성 allowlist),
  unresolved_claims.json, refuted_claims.json
"""

import argparse
import hashlib
import json
import os
import sys

import decide
import manifest as mf
import commit as cm

VALIDATE_VERSION = "0.1.0-m1b"
VALID_GRADES = {"A", "B", "C", "D", "E"}
_VERDICT_LABELS = {"entails", "neutral", "contradicts"}


# --- IO ---------------------------------------------------------------------
def _read_jsonl(path):
    records, errors = [], []
    if not os.path.exists(path):
        return records, [f"파일 없음: {path}"]
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                errors.append(f"{os.path.basename(path)}:{lineno} JSON 파싱 실패: {e}")
    return records, errors


def _read_json(path):
    if not os.path.exists(path):
        return None, [f"파일 없음: {path}"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), []
    except (OSError, json.JSONDecodeError) as e:
        return None, [f"{os.path.basename(path)} 파싱 실패: {e}"]


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# --- source registry (등급 SSOT) -------------------------------------------
def check_source_registry(sources):
    hard, by_id = [], {}
    for i, s in enumerate(sources):
        sid = s.get("id")
        if not sid:
            hard.append(f"sources.jsonl[{i}] 'id' 누락")
            continue
        if sid in by_id:
            hard.append(f"sources.jsonl: 중복 source id '{sid}'")
        by_id[sid] = s
        grade = (s.get("quality_rating") or "").strip().upper()
        if grade and grade not in VALID_GRADES:
            hard.append(f"source '{sid}': 잘못된 등급 '{grade}' (A-E만)")
    return by_id, hard


# --- verdict normalization + effective verdict ------------------------------
def normalized_verdict(v):
    """entailment_verdicts 행 → decide가 먹는 normalized_verdict."""
    if v.get("validation_error") or v.get("fail_reason") == "malformed_label":
        return "malformed"
    if v.get("span_state") == "failed":
        return "failed"
    label = v.get("label")
    return label if label in _VERDICT_LABELS else "malformed"


_PRODUCER_RANK = {"verifier": 0, "panel": 1}  # panel supersedes verifier (FR-P3)


def effective_verdicts(verdicts):
    """(claim_id, source_id)별 1개의 effective verdict로 축약. producer=panel 우선,
    그다음 span_state=done 우선. 반환: {(claim_id, source_id): verdict_row}."""
    best = {}
    for v in verdicts:
        key = (v.get("claim_id"), v.get("source_id"))
        cur = best.get(key)
        if cur is None:
            best[key] = v
            continue
        rank = (_PRODUCER_RANK.get(v.get("producer"), -1),
                1 if v.get("span_state") == "done" else 0)
        crank = (_PRODUCER_RANK.get(cur.get("producer"), -1),
                 1 if cur.get("span_state") == "done" else 0)
        if rank > crank:
            best[key] = v
    return best


# --- binding integrity (FR-A5) → exit 2 -------------------------------------
def binding_errors(verdict, claim, source):
    errs = []
    sid = verdict.get("source_id")
    if source is None:
        return [f"verdict {verdict.get('verdict_id')}: 미등록 source '{sid}'"]
    exp_snap = source.get("content_hash")
    if exp_snap and verdict.get("snapshot_hash") != exp_snap:
        errs.append(f"verdict {verdict.get('verdict_id')}: snapshot_hash 불일치 (source '{sid}')")
    exp_grade = (source.get("quality_rating") or "").strip().upper() or None
    v_grade = (verdict.get("source_grade") or "").strip().upper() or None
    if v_grade is not None and v_grade != exp_grade:
        errs.append(f"verdict {verdict.get('verdict_id')}: source_grade copy({v_grade}) != registry({exp_grade})")
    if claim is not None:
        exp_cth = claim.get("claim_text_hash")
        if exp_cth and verdict.get("claim_text_hash") and verdict["claim_text_hash"] != exp_cth:
            errs.append(f"verdict {verdict.get('verdict_id')}: claim_text_hash 불일치 (claim '{claim.get('claim_id')}')")
    return errs


# --- core join + decide -----------------------------------------------------
def validate(session, ledger_path, sources_path, out_dir, sign=False):
    art = os.path.join(session, "artifacts")
    hard = []

    sources, e = _read_jsonl(sources_path); hard += e
    by_id, e = check_source_registry(sources); hard += e
    claims, e = _read_jsonl(ledger_path); hard += e
    risk_rows, e = _read_jsonl(os.path.join(art, "risk_classifications.jsonl")); hard += e
    verdicts, e = _read_jsonl(os.path.join(art, "entailment_verdicts.jsonl")); hard += e
    partition, _pe = _read_json(os.path.join(art, "independence_partition.json"))
    # M2: panel consensus (if present, enables the panel gate, FR-P1/§6.7-4b).
    panel_rows, _pp = _read_jsonl(os.path.join(art, "panel_consensus.jsonl"))
    panel_by_claim = {r.get("claim_id"): r.get("panel_consensus") for r in panel_rows}
    m2_enabled = bool(panel_rows)

    claim_by_id = {c.get("claim_id"): c for c in claims}
    # risk: parent rows only (atomized_from is None) carry the ledger-claim verdict.
    risk_by_id = {r.get("claim_id"): r for r in risk_rows if r.get("atomized_from") is None}
    clusters = (partition or {}).get("clusters", {}) if isinstance(partition, dict) else {}

    # effective verdict per (claim, source) + binding integrity
    eff = effective_verdicts(verdicts)
    for (cid, sid), v in eff.items():
        hard += binding_errors(v, claim_by_id.get(cid), by_id.get(sid))

    if hard:
        _report_hard(hard)
        return 2

    # group effective verdicts by claim
    by_claim = {}
    for (cid, sid), v in eff.items():
        by_claim.setdefault(cid, []).append((sid, v))

    verified, unresolved, refuted = [], [], []
    coverage_gaps = []

    for claim in claims:
        cid = claim.get("claim_id")
        rc = risk_by_id.get(cid)
        is_high = bool(rc) and rc.get("computed_risk") == "high"

        if not is_high:
            # 비-high-risk: cite-and-write. 인용 소스 존재만 확인(§9).
            record = {"claim_id": cid, "status": "cite_write", "status_reason": "non_high_risk",
                      "high_risk": False, "conflict": False, "coverage_degraded": False}
            verified.append(record)
            continue

        # 복합인데 atomize 안 됨 → fail-closed (ledger-write에서 lint됐어야 함)
        if rc.get("atomic") is False:
            record = {"claim_id": cid, "status": "unresolved",
                      "status_reason": "needs_atomization", "high_risk": True,
                      "conflict": False, "coverage_degraded": False}
            unresolved.append(record)
            continue

        # §6.7 튜플
        tuples = []
        for sid, v in by_claim.get(cid, []):
            src = by_id.get(sid)
            tuples.append({
                "normalized_verdict": normalized_verdict(v),
                "anchors_ok": bool(v.get("anchors_ok")),
                "cluster_id": clusters.get(sid, sid),  # partition 없으면 source=cluster
                "quality_rating": (src.get("quality_rating") or "").strip().upper() if src else None,
                "source_id": sid,
            })

        try:
            rec = decide.decide_claim(cid, tuples, m2_enabled=m2_enabled,
                                      panel_consensus=panel_by_claim.get(cid))
        except decide.StructuralError as se:
            _report_hard([str(se)]); return 2
        rec["high_risk"] = True
        if m2_enabled:
            rec["panel_consensus"] = panel_by_claim.get(cid)

        if not by_claim.get(cid):
            coverage_gaps.append(cid)  # high-risk 주장에 verdict 0건 → missing(이미 unresolved)

        st = rec["status"]
        (verified if st == "verified" else refuted if st == "refuted" else unresolved).append(rec)

    # 커버리지 불변식(FR-X3): 모든 high-risk 주장이 결정 레코드를 가져야 함
    decided_high = {r["claim_id"] for r in (verified + unresolved + refuted) if r.get("high_risk")}
    for cid, rc in risk_by_id.items():
        if rc.get("computed_risk") == "high" and cid not in decided_high:
            _report_hard([f"커버리지 위반: high-risk claim '{cid}' 결정 누락"]); return 2

    os.makedirs(out_dir, exist_ok=True)
    _write_json(os.path.join(out_dir, "verified_claims.json"), verified)
    _write_json(os.path.join(out_dir, "unresolved_claims.json"), unresolved)
    _write_json(os.path.join(out_dir, "refuted_claims.json"), refuted)

    # FR-S1: sign the input-closure (reproducible, corruption-/skip-evident).
    enabled_producers = ["verifier"] + (["panel"] if m2_enabled else [])
    code_versions = mf.collect_code_versions(VALIDATE_VERSION)
    man = mf.build_manifest(session, enabled_producers, code_versions)
    mf.write_manifest(session, man)
    # FR-S3: stage → atomic rename runs/<run_id>/ → flip CURRENT (sole commit point).
    cm.commit_run(session, man)

    n_verified_high = sum(1 for r in verified if r.get("high_risk"))
    _report(verified, unresolved, refuted, coverage_gaps)

    # M1a: 서명 없음(M1b). verified high-risk가 0이면 정상 기권 → exit 1.
    return 1 if n_verified_high == 0 else 0


def _report_hard(errs):
    print("=== validate_ledger: HARD ERROR (exit 2) ===", file=sys.stderr)
    for e in errs:
        print(f"  - {e}", file=sys.stderr)


def _report(verified, unresolved, refuted, coverage_gaps):
    out = sys.stderr
    nv = sum(1 for r in verified if r.get("high_risk"))
    print("=== validate_ledger 결과 (§6.7) ===", file=out)
    print(f"  high-risk: verified={nv}  unresolved={len(unresolved)}  refuted={len(refuted)}  "
          f"cite_write={sum(1 for r in verified if not r.get('high_risk'))}", file=out)
    if coverage_gaps:
        print(f"  주의: verdict 없는 high-risk {len(coverage_gaps)}건 → unresolved(missing)", file=out)
    print("  → 합성은 outputs/verified_claims.json 만 근거.", file=out)


def _resolve_paths(args):
    base = args.session
    if not base:
        raise SystemExit("--session 이 필요합니다.")
    ledger = args.ledger or os.path.join(base, "artifacts", "claim_ledger.jsonl")
    sources = args.sources or os.path.join(base, "sources", "sources.jsonl")
    out_dir = args.out_dir or os.path.join(base, "outputs")
    return ledger, sources, out_dir


def main():
    p = argparse.ArgumentParser(description="받침 SOLE joiner / §6.7 decision gate (M1a)")
    p.add_argument("--session", help="리서치 세션 폴더")
    p.add_argument("--ledger")
    p.add_argument("--sources")
    p.add_argument("--out-dir")
    args = p.parse_args()
    ledger, sources, out_dir = _resolve_paths(args)
    sys.exit(validate(args.session, ledger, sources, out_dir))


if __name__ == "__main__":
    main()
