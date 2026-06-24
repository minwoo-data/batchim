# Human-label Rubric (M0 0.4) — DRAFT

Label unit: `(atomic_claim, span)`. Decide ONE of three:

- **entails** — a fluent reader, seeing ONLY this span, would agree the span
  establishes the WHOLE atomic claim (no missing qualifier/exception/scope/unit).
- **neutral** — the span is on-topic but does NOT establish the claim (missing
  scope, qualifier, different entity/number/date, or only partial support).
- **contradicts** — the span asserts something incompatible with the claim.

Edge cases:
- Quote-mining: a locally-true span that omits an exception → **neutral** (NOT entails).
- Number/date/unit mismatch (e.g. segment vs total, RRR vs ARR, FY vs CY) → **neutral** or **contradicts**.
- For the adversarial held-out subset, labelers ALSO see the full source to judge
  whether the cited span was selected to mislead (span-selection bias).

Process: ≥2 independent labelers, blind to 받침's verdict; compute Cohen's κ
(gate ≥ 0.7); adjudicate + log disagreements. Size n for a per-stratum
false-entail CI.

Status: TODO — finalize rubric with the non-author validator, then label.
