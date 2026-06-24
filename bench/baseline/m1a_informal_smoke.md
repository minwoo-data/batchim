# M1a informal smoke measurement (pre-M2, pre-human-labels)

> **Status: INFORMAL.** Not the signed M0 benchmark. Topics are the draft
> `bench/topics.json` set (not third-party-locked), "ground truth" is the
> author's known-answer (not a κ≥0.7 human-label set), single verifier (no M2
> panel), no signed manifest. This is a wiring + directional-signal run, NOT the
> pre-registered G3 comparison. See `bench/README.md` for the real protocol.

## Setup
- Pipeline run end-to-end: `dedup → classify_risk → snapshot → isolated verifier
  (fresh subagent per cited (claim,source)) → entail_gate → validate_ledger`.
- 3 topics × {1 true control + trap(s)}, 9 sources, 10 cited evidence refs.
- Real source text fetched for RFC 9001/9114 (t6), NVIDIA FY2025 IR (t3),
  EU AI Act Art 5 (t1). Quote-mining sources realistically omit the qualifier/
  exceptions.

## Result (false-entail = a should-be-blocked claim that got `verified`)

| stratum | n | false-entail | false-neg | how blocked |
|---|---|---|---|---|
| control (true claims) | 2 | 0 | 0 | verified as expected |
| fabrication | 1 | 0 | — | **code anchor** (span not in snapshot) |
| number-swap | 1 | 0 | — | **code anchor** (claim figure absent in span) + verifier |
| quote-mining (easy) | 1 | 0 | — | **verifier** caught dropped "law enforcement" scope |
| quote-mining (hard) | 1 | **1** | — | **NOT blocked** — see below |
| **total** | **6** | **1** | **0** | |

## Reading it
- **Code anchors work:** fabrication and number-swap are blocked deterministically
  regardless of the verifier — the 받침 thesis holds on these strata.
- **Easy quote-mining was caught by the verifier, not the code.** When the source
  text still carried a qualifier the overbroad claim dropped, the isolated verifier
  returned `neutral`. This is real but **unreliable** defense.
- **Hard quote-mining leaked (1 false-entail).** `c_t1_hard`: claim == cited span
  verbatim ("…is prohibited under the EU AI Act"), but real Art 5 *permits* it in 3
  exception cases. The exceptions are outside the verifier's view, so the verifier
  entails, anchors pass (verbatim + no number mismatch), and two independent B
  sources corroborate → `verified`. **This is the exact gap M2 (panel refute-lens +
  full-source labeling) must close.**

## Implication
M1a is sound where it claims to be (fabrication/number-swap, deterministic). The
single residual false-entail is a quote-mine — by design out of M1a scope. It sets
the **M2 launch-gate baseline**: the panel must drive `quote-mining` false-entail
from 1/1 → 0 on this kind of case without raising `false-negative` on controls.

## Bugs found by this run (fixed)
- `dedup.py` read `snippet`/`title` (absent in schema) → empty simhash collapsed
  all sources into one cluster. Fixed (use `text`, guard empty tokens).
- `numeric_ok` counted identifier integers ("version 1") as quantities → verified_recall
  false-negatives. Fixed (`_salient_nums`).
- `classify_risk` gazetteer `banned?` did not match "ban"/"bans" → a high-risk
  claim mis-classified `normal` (leak risk). Fixed (`ban(s|ned)?` + more verbs).
