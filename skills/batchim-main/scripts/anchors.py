#!/usr/bin/env python3
"""
anchors.py — 받침 mechanical anchors (PRD §6.3 FR-E2, Appendix B).

Pure, deterministic, NO LLM / NO network. These are the *code-enforced* part of
the gate: they guard against fabricated quotes and number/date swaps. They do
NOT (by themselves) catch quote-mining — that is the panel's job (§6.8).

  anchors_ok := span_matched AND numeric_ok
"""

import html
import re
import unicodedata

# Smart punctuation → ASCII (Appendix B step 3)
_FOLD = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...",
    " ": " ", " ": " ", " ": " ", " ": " ",
}
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Appendix B normalization, applied identically to span and snapshot.
    1) NFKC  2) decode HTML entities  3) fold smart quotes/dashes/ellipses
    4) collapse whitespace -> single space, strip  5) case-sensitive (no fold)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = html.unescape(t)
    t = "".join(_FOLD.get(ch, ch) for ch in t)
    t = _WS.sub(" ", t).strip()
    return t


def span_match(span: str, snapshot: str):
    """Return (matched: bool, char_start: int, char_end: int, occurrence_index: int).
    Contiguous substring of the normalized snapshot. Paraphrase/non-contiguous
    => no match. Coordinates are into the *normalized* snapshot; re-extraction at
    [start:end] must equal the normalized span (FR-A5)."""
    ns, nt = normalize(span), normalize(snapshot)
    if not ns:
        return (False, -1, -1, -1)
    idx = nt.find(ns)
    if idx < 0:
        return (False, -1, -1, -1)
    # occurrence_index disambiguates duplicate spans
    occ = nt.count(ns, 0, idx)  # how many occurrences strictly before idx
    return (True, idx, idx + len(ns), occ)


# --- numeric / date / unit consistency (anchor #2) --------------------------
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _nums(s: str):
    return {n.replace(",", "") for n in _NUM.findall(s or "")}


def numeric_ok(claim: str, span: str) -> bool:
    """Conservative literal numeric/date consistency: every number/year asserted
    in the CLAIM must also appear (normalized) in the SPAN. This catches number/
    year SWAPS (the anchor's job). It deliberately does NOT attempt semantic
    numeric reasoning (ranges, 'up to', RRR vs ARR, unit/fiscal-year conversion)
    — those route to the verifier/panel (PRD §6.3 note). If the claim has no
    number/year, the anchor is trivially satisfied (True)."""
    claim_nums = _nums(claim) | set(_YEAR.findall(claim or ""))
    if not claim_nums:
        return True
    span_nums = _nums(span) | set(_YEAR.findall(span or ""))
    return claim_nums.issubset(span_nums)


def anchors_ok(claim: str, span: str, snapshot: str):
    """Return (anchors_ok, detail dict) — span verbatim-present AND numbers consistent."""
    matched, start, end, occ = span_match(span, snapshot)
    nok = numeric_ok(claim, span)
    return (matched and nok), {
        "span_matched": matched, "numeric_ok": nok,
        "span_char_start": start, "span_char_end": end, "occurrence_index": occ,
    }
