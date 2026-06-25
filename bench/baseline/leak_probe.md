# leak_rate — false-entail probe (adversarial)

> **Status: INFORMAL** (author-constructed adversarial set, not the signed κ≥0.7
> benchmark). The locked, expandable companion to `control_recall.md`: that one
> measures over-abstention (rejecting TRUE claims); this measures the core failure
> the whole project exists to prevent — **a WRONG high-risk claim reaching
> `verified`** (false-entail / leak). It promotes the informal smoke's narrative
> result (false-entail 1/6 → 0/6) into a regression-tested invariant.

## Method
Each adversarial wrong claim is run through the **same production code** the gate
runs — `anchors.anchors_ok` (span/numeric/polarity) then `decide.decide_claim`
(§6.7). The upstream is set **adversarially cooperative**: the verifier `entails`,
two independent A/B sources, and — for the anchor strata — even the panel `entails`.
So if a wrong claim still does NOT verify, it is the **code** that blocked it. Each
block is attributed to the first blocking step.

- Harness: `bench/leak_probe.py` · Fixture: `bench/adversarial/leak_claims.jsonl`
  · Locked by `tests/test_leak_probe.py`.

## Result

**`leak_rate = 0/10` — no wrong claim reached `verified`.**

| wrong claim | stratum | blocked by | deterministic? |
|---|---|---|---|
| l_fabrication | fabrication (span not in source) | `anchor:span` | ✅ code |
| l_number_swap | $150B claim vs $130.5B span | `anchor:numeric` | ✅ code |
| l_number_nearmiss | $131.2B claim vs $130.5B span (0.53%) | `anchor:numeric` | ✅ code (pins the 0.05% tolerance floor) |
| l_scale_swap | $4.2B claim vs $4.2M span | `anchor:numeric` (scale) | ✅ code |
| l_percent_swap | 8% claim vs 5% span | `anchor:numeric` (pct) | ✅ code |
| l_polarity_flip | "required" vs "not required" | `anchor:polarity` | ✅ code |
| l_version_swap | TLS 1.3 claim vs TLS 1.2 span | `anchor:numeric` (ver) | ✅ code |
| l_quote_mine | verbatim, number- & polarity-consistent; drops Art 5 exceptions | `panel:contradicts` | ⚠️ panel (not code) |
| l_referent_scope | "data center revenue $130.5B" vs span "total revenue $130.5B" | `panel:contradicts` (referent flag fired) | ⚠️ panel (advisory→panel) |
| l_referent_relrisk | "relative risk cut 50%" vs span "absolute risk reduction 50%" | `panel:contradicts` (referent flag fired) | ⚠️ panel (advisory→panel) |

### Two things this locks in
1. **The 받침 thesis is now a test, not a story.** Fabrication and every number /
   scale / percent / version swap are blocked **deterministically by a code anchor —
   even with the verifier AND panel fooled into `entails`**. No LLM judgment is
   trusted for these strata.
2. **The ver-class recall fix did not open a leak.** `l_version_swap` (claim "TLS
   1.3" vs a span carrying "TLS 1.2") is still caught by `numeric_ok` — because the
   span *carries the competing version*, the `ver` class fires as a CONFLICT. The
   recall fix only relaxed the pure-omission case; swap protection is intact.

### The one non-deterministic block — and why it's fenced
`l_quote_mine` passes all code anchors (it's a real, verbatim, number-consistent
quote). Only the **panel's refute lens** blocks it (consensus `contradicts`, citing
the dropped Art 5 law-enforcement exceptions). The probe proves the panel is
**load-bearing**: `l_quote_mine_no_panel` repeats the identical claim with the panel
DISABLED and it **LEAKS to `verified`** (anchors pass, two A/B sources entail). That
is the exact M2 launch-gate dependency — quote-mining is the one stratum the code
half cannot close, so a run without the panel is unsafe for this class.

### Referent mismatch — exercising a built-but-unmeasured defense
`anchors.referent_flags` already detects same-number-different-REFERENT overreach
(segment vs total, relative vs absolute risk, fiscal vs calendar, gross vs net), but
no probe touched it. It is **advisory by design** — it does NOT fail `anchors_ok`; it
rides along in the verdict and routes to the panel's numeric lens. So a referent
overreach behaves exactly like quote-mining: anchors pass, the panel must catch it.
- `l_referent_scope` ("data center revenue $130.5B" cited to "total revenue $130.5B")
  and `l_referent_relrisk` ("relative risk cut 50%" cited to "absolute risk reduction
  50%") both PASS anchors (same number) with the referent flag firing, then are
  blocked by `panel:contradicts`.
- `l_referent_scope_no_panel` (panel disabled) **LEAKS** — confirming the panel is
  load-bearing for referent overreach too, not just quote-mining.
This closes a measurement gap: the referent_flags → panel pathway now has probe
coverage and a regression test, so it can't silently rot.

## Bottom line
- Deterministic strata (fabrication / number / scale / percent / polarity / version):
  **0 leak, code-enforced, fooled-upstream-proof.**
- Non-deterministic strata (quote-mining + referent overreach): **0 leak with the
  panel, LEAK without it** — the panel is mandatory, as designed. Strengthening the
  panel (model diversity, retry-before-quarantine, contrary-retrieval) directly hardens
  every stratum the code half cannot close.
- This is the floor to defend when evaluating any ANCHOR LOOSENING: re-run
  `leak_probe.py` and require `leak_rate` stays 0. **Already exercised:** the 0.05%
  numeric rounding tolerance (added so `$130.5B` anchors to `$130,497M`) was shipped
  only after `l_number_nearmiss` (a 0.53% swap) confirmed the floor still blocks
  near-miss swaps — recall recovered, `leak_rate` unchanged at 0.
