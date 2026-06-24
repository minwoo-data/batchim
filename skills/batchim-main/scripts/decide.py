#!/usr/bin/env python3
"""
decide.py — 받침 §6.7 decision algorithm (the "decide" stage of validate_ledger, D5).

Pure function over a claim's effective-verdict tuples. NO I/O, NO crypto — so it
is golden-fixture testable independent of signing (PRD D5). validate_ledger.py
calls this after join + producer-aware supersession (effective_verdict).

A tuple (one per (claim, source)):
  { "normalized_verdict": "entails|neutral|contradicts|failed|malformed|missing",
    "anchors_ok": bool, "cluster_id": str, "quality_rating": "A|B|C|D|E",
    "source_id": str }
Derivation (caller or here): failed|malformed|missing OR anchors_ok=False
=> counts as NEUTRAL (cannot promote/refute/conflict), but is recorded.

Returns a verified_claims.json record (PRD Appendix A).
"""

DECISION_TABLE_VERSION = "0.1.0-m1a"
_AB = {"A", "B"}
_PROMOTABLE = {"entails", "contradicts"}  # only these, and only if anchored


class StructuralError(Exception):
    """Maps to exit 2 (PRD §6.7 step 1 / FR-X1)."""


def _effective_label(t):
    """Apply the §6.7 normalization: non-promotable verdicts and anchor-failed
    labels count as neutral."""
    v = t.get("normalized_verdict")
    if v in ("failed", "malformed", "missing"):
        return "neutral"
    if v in _PROMOTABLE and not t.get("anchors_ok"):
        return "neutral"  # anchor-failed entails/contradicts cannot count
    return v if v in ("entails", "neutral", "contradicts") else "neutral"


def decide_claim(claim_id, tuples, m2_enabled=False, panel_consensus=None,
                 skipped_budget=False):
    """§6.7 ordered algorithm. `panel_consensus` ∈ {entails,neutral,contradicts,None}
    is the claim-level 2-of-3 panel result (required for `verified` when m2_enabled).
    Raises StructuralError for the caller to map to exit 2."""
    base = {"claim_id": claim_id, "conflict": False, "coverage_degraded": bool(skipped_budget),
            "independent_entails": 0, "panel_consensus": panel_consensus,
            "proof_source_ids": [], "proof_grades": [], "refuted_by": None}

    # step 0 — missing: no tuples at all => terminal unresolved(missing)
    if not tuples:
        return {**base, "status": "unresolved",
                "status_reason": "skipped_budget" if skipped_budget else "missing"}

    # step 1 — structural integrity (orphan/schema/binding) is checked upstream
    # (FR-A5); a tuple flagged structural here aborts the whole run.
    for t in tuples:
        if t.get("structural_error"):
            raise StructuralError(f"{claim_id}: {t['structural_error']}")

    eff = [(t, _effective_label(t)) for t in tuples]
    entails = [t for t, l in eff if l == "entails"]
    contradicts = [t for t, l in eff if l == "contradicts"]
    ab_contradicts = [t for t in contradicts if (t.get("quality_rating") or "").upper() in _AB]

    # A claim-level panel "entails" consensus (M2) adjudicates the dispute and
    # overturns contradiction-based blocking (both refuted and conflict) — FR-P3.
    panel_override = m2_enabled and panel_consensus == "entails"

    # step 2 — refuted: >=1 anchored A/B contradicts (unless panel overturns).
    if ab_contradicts and not panel_override:
        return {**base, "status": "refuted",
                "status_reason": "ab_contradiction",
                "refuted_by": [t.get("source_id") for t in ab_contradicts]}

    # step 3 — conflict: >=1 anchored entails AND >=1 anchored contradicts (any grade)
    if entails and contradicts and not panel_override:
        return {**base, "status": "unresolved", "status_reason": "conflict",
                "conflict": True}

    # step 4 — verified: >=2 anchored entails from DISTINCT clusters,
    #   incl. >=1 A/B within the entailing set; AND (M2) panel 2-of-3 == entails.
    clusters = {}
    for t in entails:
        clusters.setdefault(t.get("cluster_id"), t)  # one representative per cluster
    distinct = list(clusters.values())
    has_ab = any((t.get("quality_rating") or "").upper() in _AB for t in distinct)
    panel_ok = (not m2_enabled) or (panel_consensus == "entails")
    if len(distinct) >= 2 and has_ab and panel_ok:
        return {**base, "status": "verified", "status_reason": "ok",
                "independent_entails": len(distinct),
                "proof_source_ids": [t.get("source_id") for t in distinct],
                "proof_grades": [(t.get("quality_rating") or "").upper() for t in distinct]}

    # step 5 — otherwise unresolved
    reason = "insufficient_independent_entails"
    if m2_enabled and not panel_ok and len(distinct) >= 2 and has_ab:
        reason = "panel_no_consensus"
    return {**base, "status": "unresolved", "status_reason": reason,
            "independent_entails": len(distinct)}
