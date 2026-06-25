# verified_recall — over-abstention measurement (control-heavy)

> **Status: INFORMAL** (author known-answer, not the signed κ≥0.7 benchmark). This
> is the mirror of `m1a_informal_smoke.md`: that one measured **false-entail**
> (wrong claim passes); this measures **over-abstention** — does the gate reject
> TRUE, well-evidenced high-risk claims? A gate that abstains on everything has
> leak_rate 0 and is useless, so `verified_recall = verified ÷ should-verify` is a
> launch metric (PRD §9).

## Method
Drive a control-heavy fixture of *genuinely-true* high-risk claims (RFC specs, an
SEC filing, peer-reviewed vaccine-efficacy numbers) with correct cited spans through
the **same production code** the real gate runs — `anchors.anchors_ok`
(span/numeric/polarity) then `decide.decide_claim` (§6.7). NO LLM, NO network: the
verifier/panel votes are the *ideal cooperating* upstream (a true claim's correct
verifier verdict is `entails`, panel consensus `entails`), so **every miss is the
gate's own over-rejection**, isolated from LLM noise. Misses are attributed to the
first blocking step in pipeline order.

- Harness: `bench/verified_recall.py` · Fixture: `bench/control/control_claims.jsonl`
  (12 headline + 7 single-cause diagnostic probes) · Locked by `tests/test_verified_recall.py`.
- **Headline** rows = true claims whose cited evidence is *adequate by policy*
  (≥2 distinct clusters incl ≥1 A/B). A miss there is a pure bug.
- **Diagnostic** rows isolate one policy/edge over-rejection each; reported
  separately so they don't contaminate the headline number.

## Result

| | before fix | after fix |
|---|---|---|
| **headline verified_recall** | **8/12 = 0.667** | **12/12 = 1.000** |

### Ranked over-rejection causes (before fix)
| n | cause | claims | verdict |
|---|---|---|---|
| 5 | `anchor:numeric` | c_tls13_pfs, c_rfc1918_private, c_oauth_bearer, d_nvda_rounded, d_polarity_fp* | **real bug (3) + 2 diagnostics** |
| 2 | `anchor:span` | c_nvda_rev, d_paraphrase | 1 fixture error + 1 diagnostic |
| 2 | `independence:lt2_clusters` | d_single_primary, d_syndicated | policy (by design) |
| 1 | `independence:no_ab_grade` | d_grade_floor | policy (by design) |
| 1 | `panel:no_consensus` | d_panel_split | policy (by design) |

\* d_polarity_fp's numeric was incidental; its designed cause is `anchor:polarity`.

## The bug: numeric anchor over-rejected version / identifier numbers

`anchors._quantities` let `is_decimal` / `is_year` **win over identifier context**,
so three classes of non-quantity number became *required* quantities that a true
proof span had to restate:

1. **Version decimals** — `TLS 1.3`, `OAuth 2.0`. A span that proves the property
   ("all key exchange provides forward secrecy") without echoing the version failed
   `numeric_ok`. (Cost: c_tls13_pfs, c_oauth_bearer; made c_tls13_1rtt pass only
   because its span happened to restate "1.3" — fragile.)
2. **Standard numbers that look like years** — `RFC 1918`: 1918 ∈ [1800,2099] was
   read as a *year* and required in the span. (Cost: c_rfc1918_private.)

These trace to the maintainers' explicit prior choice ("quantity signals win over
context, so TLS version 1.3 keeps 1.3") which optimized version-swap detection at
the measured cost of ~25% headline recall.

### Fix (commit) — `ver` class, conflict-only; identifier years dropped
- A **unit-less decimal** is a `ver`-class label, not a measured quantity. `ver` is
  **conflict-only** in `numeric_ok`: it fails only when the span carries a *different*
  version (1.2 vs 1.3) — a pure omission ("span doesn't restate TLS 1.3") passes, and
  entailment is left to the verifier/panel (defense-in-depth).
- **Identifier context drops year-form numbers** too (an RFC number is not a year).
- Measured units (`pct` / `mag` / `year`) keep omission-fail semantics unchanged, so
  number/scale/percent **swaps are still caught deterministically**.

**Swap protection preserved** — verified by existing `test_gate_core`:
`numeric_ok("…TLS version 1.2…", "older than 1.3")` still `False` (span carries the
competing 1.3 → conflict). New regressions in `test_numeric_version_recall`. Full
suite green (21 files / 363 assertions, was 334).

## The four over-rejections we did NOT "fix" — they are policy, not bugs
The remaining causes are §6.7 working as specified. Surfaced here as trade-offs for
the launch-gate decision, **not** loosened unilaterally (loosening any of them
re-opens a false-entail path the gate exists to close):

| cause | true claim it rejects | the trade-off if relaxed |
|---|---|---|
| `independence:lt2_clusters` | a claim backed by **one** authoritative primary (single RFC) → unresolved | single-source verify re-opens the "one wire story, echoed" false-entail; keep ≥2 clusters. Possible narrow carve-out: an A-grade *primary* (standards body / filer) as its own sufficient cluster — needs a false-entail measurement first. |
| `independence:no_ab_grade` | true claim cited only to C/D blogs | grade floor is the point; fix is better sourcing, not a lower floor. |
| `panel:no_consensus` | true claim where one lens failed/abstained | **DONE** — `panel.py` now retries-before-quarantine (a `done` vote supersedes a `failed` one; success never clobbered by a later failure). Precision-safe; consensus rule untouched. |
| `anchor:numeric` (rounding) | `$130.5B` vs exact `$130,497M` | **DONE** — a 0.05% same-scale, same-class tolerance (`NUMERIC_REL_TOL`) recovers lower-precision-but-true claims (mag/pct only; year/ver stay exact). Measured safe: `leak_probe` `leak_rate` stayed **0** after adding a near-miss swap probe (`l_number_nearmiss`, 0.53% = 10× the floor → still blocked). |
| `anchor:polarity` (distributed negation) | "does **not** support" vs "**no longer** supported" | `polarity_ok` uses window-1 adjacency for precision; "no longer X" isn't adjacent. Widening the window risks polarity false-*negatives* (missed real inversions). Leave; the verifier handles it. |

## Bottom line
- The gate's **intrinsic** over-abstention (anchors, given cooperating upstream) was a
  small set of fixable issues, now all closed: version/identifier numbers (`ver` class),
  the rounding tolerance, and panel-lens retry. Headline verified_recall **0.667 → 1.000**
  (now 13/13, incl. the recovered rounding case), with the false-entail floor held at
  **`leak_rate` 0** the whole time (`bench/baseline/leak_probe.md`, near-miss swaps pinned).
- The remaining over-abstention is **deliberate §6.7 conservatism** (independence ≥2
  clusters / A-B grade floor) — it trades recall for the false-entail guarantees and
  should not move without a measured precision cost on the **signed** benchmark (the one
  still-blocking dependency: real κ≥0.7 human labels).
