#!/usr/bin/env python3
"""contrary.py — 받침 contrary-retrieval lens helper (PRD §6.8 Q6; M2 panel upgrade).

The single isolated verifier and the reasoning-only refute lens can both miss
quote-mining-by-OMISSION: the cited span is true, but a *material qualifier/exception
that lives elsewhere* makes the unqualified claim wrong. The strongest defense is to
**actively go look for the refutation** instead of reasoning over the given sources.

This module is the deterministic half of that lens:
  - generate_refutation_queries(claim) → search queries aimed at exceptions /
    contradictions / corrections (the orchestrator runs them via WebSearch/WebFetch).
  - aggregate(findings) → a panel vote (entails | neutral | contradicts) from what
    the search turned up, so the lens plugs straight into panel.py as the `refute` vote.

NFR-5: with no search backend the lens degrades to reasoning-only (queries unused);
the panel still has its other two lenses.
"""

import re

_WORD = re.compile(r"[0-9A-Za-z가-힣]+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
         "was", "were", "be", "by", "with", "that", "this", "it", "its", "as", "at",
         "all", "any", "under", "from", "into", "real", "time"}
# operators that surface a dropped qualifier / a refutation / a correction
_REFUTE_OPS = ["exceptions", "unless", "except", "limitations", "caveats",
               "however criticism", "disputed", "challenged", "overturned",
               "is false", "not true", "myth", "correction", "retracted", "walked back"]


def _keyterms(text, n=8):
    seen, out = set(), []
    for t in _WORD.findall((text or "").lower()):
        if len(t) >= 3 and t not in _STOP and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= n:
            break
    return out


def generate_refutation_queries(claim, max_q=10):
    """Deterministic refutation-seeking queries: a direct fact-check phrasing plus
    key-terms × refutation operators. Designed to surface the exception the claim
    omits (the quote-mining failure mode)."""
    claim = (claim or "").strip().rstrip(".")
    key = _keyterms(claim)
    key_str = " ".join(key)
    queries = []
    if claim:
        queries.append(f"is it true that {claim}")
    if key_str:
        queries.append(f"{key_str} exceptions OR limitations")
        queries.extend(f"{key_str} {op}" for op in _REFUTE_OPS)
    # dedupe, preserve order, cap
    seen, out = set(), []
    for q in queries:
        if q not in seen:
            seen.add(q)
            out.append(q)
        if len(out) >= max_q:
            break
    return out


_AB = {"A", "B"}


def aggregate(findings):
    """findings: [{refutes:bool, qualifies:bool, quality_rating:'A'..'E', summary}].
    Map the search result to a panel vote:
      - any adequately-graded finding that REFUTES the claim          → contradicts
      - any that adds a MATERIAL QUALIFIER the claim omits (quote-mine) → contradicts
        (the claim as stated is not supported)
      - searched, found nothing contrary                              → entails
      - nothing searched / inconclusive                               → neutral
    Returns {"vote", "reason", "evidence": [...]}."""
    if not findings:
        return {"vote": "neutral", "reason": "no_contrary_search", "evidence": []}
    hits = []
    for f in findings:
        grade = (f.get("quality_rating") or "").upper()
        ok_grade = grade in _AB or not grade  # ungraded counts (conservative)
        if (f.get("refutes") or f.get("qualifies")) and ok_grade:
            hits.append(f)
    if hits:
        kind = "refuted" if any(h.get("refutes") for h in hits) else "material_qualifier_omitted"
        return {"vote": "contradicts", "reason": kind,
                "evidence": [h.get("summary", "") for h in hits[:3]]}
    return {"vote": "entails", "reason": "no_contrary_evidence_found", "evidence": []}
