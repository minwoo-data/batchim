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
# scale words (so $4.2bn ≠ $4.2 million) and percent (so 8% ≠ 8)
_MAGNITUDE = {"bn": 1e9, "b": 1e9, "billion": 1e9, "m": 1e6, "mm": 1e6, "million": 1e6,
              "k": 1e3, "thousand": 1e3, "tn": 1e12, "t": 1e12, "trillion": 1e12}
_MAG_AFTER = re.compile(r"^\s*(bn|billion|mm|million|thousand|trillion|[bmkt])\b", re.I)
_PCT_AFTER = re.compile(r"^\s*(?:%|(?:percent|pct|퍼센트)\b)", re.I)
# mutually-exclusive referents: a number that matches literally may still describe a
# DIFFERENT quantity (segment vs total, fiscal vs calendar, RRR vs ARR). Advisory →
# routed to the panel's numeric lens (PRD §6.3 note), not a hard anchor fail.
_REFERENT_GROUPS = [
    ("scope", ["total", "overall", "company-wide", "companywide", "consolidated", "group-wide"],
              ["segment", "division", "data center", "data-center", "business unit", "product line"]),
    ("fiscal_calendar", ["fiscal"], ["calendar"]),
    ("period", ["annual", "full-year", "full year", "yearly"], ["quarterly", "quarter"]),
    ("risk", ["relative risk", "relative reduction"], ["absolute risk", "absolute reduction"]),
    ("margin", ["gross"], ["net"]),
]


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
    """All bare numbers in `s` (legacy helper)."""
    return {n.replace(",", "") for n in _NUM.findall(s or "")}


def _canon_value(v):
    return str(int(v)) if v == int(v) else repr(round(v, 6)).rstrip("0").rstrip(".")


def _quantities(text: str):
    """Salient quantities normalized by SCALE and unit-class, so a scale/percent
    mismatch is caught even when the bare digits coincide ($4.2bn vs $4.2 million,
    8% vs 8). Returns tokens `cls:value` with cls ∈ {pct, year, mag, ver}:
      - pct/year/mag are MEASURED values (omission-fails in `numeric_ok`); currency
        and plain numbers fold to `mag`, so $4.2bn matches "4.2 billion" but NOT
        "$4.2 million".
      - **ver** = a unit-less decimal used as a VERSION/ratio label ("TLS 1.3",
        "OAuth 2.0", "version 1.2"). It is NOT a measured quantity: a true proof
        span often establishes the property without restating the version, so `ver`
        is CONFLICT-only in `numeric_ok` (fails only when the span carries a DIFFERENT
        version) — this is the verified_recall fix for version-identifier decimals.
    Identifier/ordinal *integers* and year-form numbers in identifier context
    ("version 1", "RFC 1918", "Section 12", "HTTP/3") are dropped — an RFC number is
    not a measured year. (Decimals with a unit, e.g. "$4.2" or "1.3%", stay measured.)"""
    out = set()
    for m in _NUM.finditer(text or ""):
        tok = m.group().replace(",", "")
        start, end = m.span()
        before, after = text[:start], text[end:]
        is_decimal = "." in tok
        is_year = bool(_YEAR_RE.fullmatch(tok))
        pct = bool(_PCT_AFTER.match(after))
        mag_m = _MAG_AFTER.match(after)
        has_unit = (pct or bool(mag_m) or bool(_UNIT_AFTER.match(after))
                    or bool(_CUR_BEFORE.search(before)))
        attached = start > 0 and (text[start - 1] in "/-#" or text[start - 1].isalpha())
        ident_ctx = attached or bool(_IDENT_BEFORE.search(before))
        multidigit = len(tok.replace(".", "")) >= 2
        val = float(tok)
        if has_unit:                          # measured: $4.2bn, 8%, 1.3%, 500 million
            if pct:
                out.add(f"pct:{_canon_value(val)}")
            else:
                if mag_m:
                    val *= _MAGNITUDE[mag_m.group(1).lower()]
                out.add(f"mag:{_canon_value(val)}")
        elif is_decimal:                      # unit-less decimal → version/ratio label
            out.add(f"ver:{_canon_value(val)}")
        elif ident_ctx:
            continue                          # "version 1", "RFC 1918", "Section 12" → drop
        elif is_year:
            out.add(f"year:{_canon_value(val)}")
        elif multidigit:
            out.add(f"mag:{_canon_value(val)}")
        # else: bare single digit, no unit → drop
    return out


def referent_flags(claim: str, span: str):
    """Detect mutually-exclusive referents present on opposite sides (claim says
    'data center', span says 'total'; claim 'fiscal', span 'calendar'). ADVISORY —
    surfaced for the panel's numeric lens, does NOT change anchors_ok."""
    cl, sp = (claim or "").lower(), (span or "").lower()
    flags, seen = [], set()
    for name, side_a, side_b in _REFERENT_GROUPS:
        for x in side_a:
            for y in side_b:
                for c_term, s_term in ((x, y), (y, x)):
                    if c_term in cl and s_term in sp and (name, c_term, s_term) not in seen:
                        seen.add((name, c_term, s_term))
                        flags.append({"group": name, "claim_term": c_term, "span_term": s_term})
    return flags


_WORD_RE = re.compile(r"[0-9A-Za-z가-힣']+")
_NEG_ADJ = {"not", "never", "cannot", "neither", "nor", "without", "no"}
_KO_NEG = ("않", "못", "아니", "없")


def _is_neg(tok: str) -> bool:
    t = tok.lower()
    return t in _NEG_ADJ or t.endswith("n't") or any(k in tok for k in _KO_NEG)


def _stem(t: str) -> str:
    return t.lower()[:5]


def _neg_adjacent(tokens, stem):
    """Is the first content token with this stem immediately preceded by a negation?
    Window = 1 (direct adjacency) keeps precision high: 'is NOT prohibited' fires,
    'did not block the merger' does not flip 'merger' (its neighbor is 'the')."""
    for i, t in enumerate(tokens):
        if len(t) >= 4 and _stem(t) == stem:
            return i > 0 and _is_neg(tokens[i - 1])
    return False


def polarity_ok(claim: str, span: str) -> bool:
    """Reject a span that NEGATES what the claim asserts (or vice versa) on a shared
    predicate: 'X is prohibited' vs 'X is not prohibited'. High precision via
    direct-adjacency negation + 5-char stem; a shared content stem negated on
    exactly one side ⇒ polarity mismatch ⇒ the span cannot support the claim. No
    shared content stem ⇒ True (nothing to compare)."""
    ct = _WORD_RE.findall(claim or "")
    st = _WORD_RE.findall(span or "")
    cstems = {_stem(t) for t in ct if len(t) >= 4}
    sstems = {_stem(t) for t in st if len(t) >= 4}
    for stem in (cstems & sstems):
        if _neg_adjacent(ct, stem) != _neg_adjacent(st, stem):
            return False
    return True


def numeric_ok(claim: str, span: str) -> bool:
    """Scale/unit-aware numeric consistency. Two regimes (see `_quantities`):
      - MEASURED quantities (pct/mag/year): every one asserted in the CLAIM must
        appear in the SPAN at the same scale/unit class — omission OR mismatch fails
        (so $4.2bn ≠ $4.2 million, 8% ≠ bare 8). Catches number/scale/percent SWAPS.
      - VERSION decimals (ver): CONFLICT-only — a claim version fails only when the
        span carries a DIFFERENT version (1.2 vs 1.3). If the span simply omits the
        version (it proves the property without restating "TLS 1.3"), that is NOT a
        swap → it passes here and entailment is left to the verifier/panel. This is
        the verified_recall fix: version-identifier decimals no longer over-reject
        true claims whose proof span doesn't echo the version number.
    Referent mismatch (segment vs total etc.) is advisory (`referent_flags`), routed
    to the panel, not failed here. No claim quantity ⇒ True."""
    cq, sq = _quantities(claim), _quantities(span)
    c_hard = {q for q in cq if not q.startswith("ver:")}
    s_hard = {q for q in sq if not q.startswith("ver:")}
    if not c_hard.issubset(s_hard):
        return False
    span_vers = {q.split(":", 1)[1] for q in sq if q.startswith("ver:")}
    if span_vers:  # span asserts version(s): a claim version must be one of them
        for q in cq:
            if q.startswith("ver:") and q.split(":", 1)[1] not in span_vers:
                return False
    return True


def anchors_ok(claim: str, span: str, snapshot: str):
    """Return (anchors_ok, detail dict) — span verbatim-present AND numbers (scale/
    unit) consistent. `referent_flags` is advisory metadata (→ panel), not part of
    the boolean."""
    matched, start, end, occ = span_match(span, snapshot)
    nok = numeric_ok(claim, span)
    pol = polarity_ok(claim, span)
    return (matched and nok and pol), {
        "span_matched": matched, "numeric_ok": nok, "polarity_ok": pol,
        "span_char_start": start, "span_char_end": end, "occurrence_index": occ,
        "referent_flags": referent_flags(claim, span),
    }
