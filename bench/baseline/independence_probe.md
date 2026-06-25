# independence-partition probe (adversarial)

> **Status: INFORMAL** (author-constructed). The third measurement probe, after
> `control_recall.md` (over-abstention) and `leak_probe.md` (false-entail). Those
> exercise the ANCHOR layer; this exercises the layer `decide.py` *depends on* — the
> independence partition. `decide` grants `verified` only on **≥2 distinct clusters
> (incl ≥1 A/B)**, so if clustering is foolable the "two independent sources agree"
> guarantee is hollow.

## Method
Run each scenario's sources through the **real composed chain**
`dedup.partition → semantic.semantic_refine → provenance.provenance_refine` (SKILL.md
Phase 4.5 order; semantic uses its deterministic lexical-fallback embedder — no
network). Then LINK to the gate: build a claim where every source entails (anchored,
A/B) and run `decide.decide_claim` on the resulting clusters — a collapse failure
shows up as a *manufactured* `verified`.

Two failure directions are measured:
- **fake independence** (security): a syndicated/duplicated set that should be ONE
  cluster stays ≥2 → manufactures corroboration → leak.
- **over-merge** (recall): genuinely independent sources merged → a true claim loses
  its second cluster → over-abstention.

- Harness: `bench/independence_probe.py` · Fixture:
  `bench/adversarial/independence_claims.jsonl` · Locked by
  `tests/test_independence_probe.py`.

## Result

**`fake_independence_rate = 0/5` · `over_merge_rate = 0/2`** — and 0 manufactured `verified`.

| scenario | kind | sources → clusters | collapsed by |
|---|---|---|---|
| ip_canonical_url | collapse | 2 → 1 | dedup (canonical URL; tracking params stripped) |
| ip_verbatim_syndication | collapse | 3 → 1 | dedup (simhash near-dup) |
| ip_same_wire | collapse | 2 → 1 | provenance (shared wire) |
| ip_same_byline | collapse | 2 → 1 | provenance (shared byline) |
| ip_paraphrase_with_wire | collapse | 2 → 1 | provenance (wire backstops the missed paraphrase) |
| ip_independent_distinct | separate | 2 → 2 | — (genuine independence preserved) |
| ip_primary_plus_analysis | separate | 2 → 2 | — (A primary + B analysis → legit ≥2) |

### What this locks in
The "≥2 independent clusters" requirement is **not foolable by the common
syndication vectors**: identical-URL reposts, verbatim wire copies, and shared
wire/byline all collapse to one cluster *deterministically* — so a single story can't
manufacture independent corroboration, and `decide` cannot be tricked into `verified`
on them. Genuine independence is preserved (no over-merge), so the requirement
doesn't over-abstain on real two-source agreement.

## The residual gap — bare paraphrase needs an embedding backend (or provenance)
`ip_paraphrase_bare` is the independence analogue of `leak_probe`'s quote-mine: a
reworded copy of one wire story with **no shared URL/wire/byline**. The lexical-
fallback embedder scores the pair at cosine **~0.55** — below the 0.80 merge
threshold — so it is **NOT collapsed** and fakes two independent sources. (The
`semantic.py` docstring's "paraphrase ~0.84" is optimistic for genuinely reworded
text; realistic paraphrase lands much lower on the fallback.)

This is a **backend-quality gap, not a logic bug**: the probe confirms a real
embedding backend (stubbed as a perfect paraphrase detector) **does** collapse the
pair. Two existing mitigations already cover the common case:
1. **Provenance** — real syndicated paraphrases almost always carry the same
   wire/byline (see `ip_paraphrase_with_wire`, which collapses); the bare case needs
   genuinely independent-looking metadata on a copied story, which is rarer.
2. **A real embedding backend** (NFR-5 pluggable) closes it directly.

### Recommendations (measured, not assumed)
- **Cheap, precision-safe:** lower/empirically-recalibrate the lexical-fallback
  threshold, OR — better — emit a `low_confidence_independence` flag when two clusters
  are within (threshold − margin) cosine, and route them to the panel's
  `source_quality` lens instead of trusting them as independent. (Requires its own
  leak/recall measurement before shipping.)
- **Deployment guidance:** for high-stakes runs, configure a real embedding backend;
  the fallback is a reproducibility convenience, not a paraphrase-grade detector.
- **Do NOT** raise the threshold to force collapse — that would over-merge genuinely
  independent sources (recall loss). The fix is a better signal, not a blunter one.

## Bottom line
- Deterministic independence signals (URL / verbatim / wire / byline):
  **0 fake independence, 0 over-merge, 0 manufactured `verified`.**
- Bare paraphrase: the one stratum the deterministic + fallback layers miss — closed
  by provenance in the common case and by a real embedding backend in general; the
  residual is surfaced and flagged, not silently trusted. Mirrors quote-mine→panel:
  the hard case needs the stronger (model-backed) layer.
