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

## File schema & tooling
- `unit_id = "<claim_id>::<source_id>"` (one cited span = one unit).
- Each labeler writes `bench/labels/labeler_<name>.jsonl`:
  `{"unit_id":"clm_001::src_003","label":"entails|neutral|contradicts","note":"…"}`
- **κ gate:** `python bench/kappa.py` → per-pair Cohen's κ + disagreement list,
  exits non-zero unless min pairwise κ ≥ 0.7. Below the gate ⇒ refine edge-cases
  and re-label (don't adjudicate a noisy set).
- **Adjudicate** the listed disagreements → `bench/labels/gold.jsonl` (same schema).
- **Score:** `python bench/score_benchmark.py --session <run> --gold gold.jsonl
  --strata strata.json` → false-entail / precision / recall, **stratified by
  failure-mode** (`strata.json` = `{claim_id: fabrication|number-swap|quote-mining|control}`).
  It runs the gold labels through the same §6.7 `decide.py`, so gold_status is
  apples-to-apples with the system status.

Status: TODO — finalize rubric with the non-author validator, then label. Tooling
(`kappa.py`, `score_benchmark.py`) is ready and tested.
