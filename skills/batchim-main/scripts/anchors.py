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
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_YEAR_RE = re.compile(r"(?:1[89]\d{2}|20\d{2})")
# A number is an IDENTIFIER (not a required quantity) when an identifier word
# precedes it ("version 1", "Article 5", "RFC 9114", "Section 12") ...
_IDENT_BEFORE = re.compile(
    r"(?:version|ver|article|art|section|sec|chapter|ch|clause|paragraph|para|"
    r"rule|figure|fig|table|item|no|number|rfc|iso|ieee|part|step|phase|tier|"
    r"level|grade|type|class|page|vol|volume|edition|appendix|annex)\.?\s*$", re.I)
# ... or a unit/currency marks it as a QUANTITY to keep.
_UNIT_AFTER = re.compile(
    r"^\s*(?:[%°]|(?:percent|bn|billion|million|trillion|thousand|[mkbt]|"
    r"usd|eur|gbp|krw|won|dollars?|euros?|pounds?|kg|km|mph|[gm]hz|[mgt]b|"
    r"degrees?|years?|months?|days?|hours?|people|cases?|deaths?|pts?|bps)\b)", re.I)
_CUR_BEFORE = re.compile(r"[$€£¥₩]\s*$")


def _salient_nums(text: str):
    """Quantities in `text` that a proof span must contain — dropping identifier/
    ordinal numbers ("QUIC version 1", "HTTP/3", "Section 12") that are not the
    claim's measured value. Kept: decimals, years, unit/%/currency-adjacent, and
    multi-digit integers outside identifier context. Dropped: bare single-digit
    integers and identifier-context numbers. (Quantity signals win over context,
    so "TLS version 1.3" keeps 1.3.)"""
    out = set()
    for m in _NUM.finditer(text or ""):
        tok = m.group().replace(",", "")
        start, end = m.span()
        before, after = text[:start], text[end:]
        is_decimal = "." in tok
        is_year = bool(_YEAR_RE.fullmatch(tok))
        has_unit = bool(_UNIT_AFTER.match(after)) or bool(_CUR_BEFORE.search(before))
        attached = start > 0 and (text[start - 1] in "/-#" or text[start - 1].isalpha())
        ident_ctx = attached or bool(_IDENT_BEFORE.search(before))
        multidigit = len(tok.replace(".", "")) >= 2
        if is_decimal or is_year or has_unit:
            out.add(tok)            # quantity signal wins (even in identifier context)
        elif ident_ctx:
            continue                # identifier / ordinal → not a required quantity
        elif multidigit:
            out.add(tok)            # multi-digit non-identifier integer → quantity
        # else: bare single-digit, no unit → identifier/ordinal → drop
    return out


def _nums(s: str):
    """All numbers in `s` (span side of the subset test) — identifiers included,
    so a claim quantity can be found wherever it occurs."""
    return {n.replace(",", "") for n in _NUM.findall(s or "")}


def numeric_ok(claim: str, span: str) -> bool:
    """Conservative literal numeric/date consistency: every QUANTITY asserted in
    the CLAIM must also appear (normalized) in the SPAN. Catches number/year SWAPS
    (the anchor's job) while ignoring identifier/ordinal numbers ("version 1") so
    they don't cause false anchor failures (verified_recall loss). Does NOT attempt
    semantic reasoning (ranges, 'up to', RRR vs ARR, unit/fiscal-year conversion)
    — those route to the verifier/panel (PRD §6.3). No claim quantity ⇒ True."""
    claim_nums = _salient_nums(claim)
    if not claim_nums:
        return True
    return claim_nums.issubset(_nums(span))


def anchors_ok(claim: str, span: str, snapshot: str):
    """Return (anchors_ok, detail dict) — span verbatim-present AND numbers consistent."""
    matched, start, end, occ = span_match(span, snapshot)
    nok = numeric_ok(claim, span)
    return (matched and nok), {
        "span_matched": matched, "numeric_ok": nok,
        "span_char_start": start, "span_char_end": end, "occurrence_index": occ,
    }
