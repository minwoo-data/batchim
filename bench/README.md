# 받침 Benchmark (M0)

The evidence base for the moat (PRD G3): a **pre-registered, signed** benchmark
where 받침 is measured against the `insane-research` baseline on **human-labeled**
entailment, **stratified by failure-mode**. Everything here is frozen and hashed
into the signed manifest at M0 (PRD FR-S1) before any tuning.

## Anti-gaming rules (PRD §8, §9, R7)
1. **Topic selection is criteria-based, not author cherry-pick.** Topics must
   satisfy the published criteria below; the final set should be validated by a
   third party (or selected by a non-author) so the failure-mode mix can't be
   tilted toward cases 받침 happens to win (e.g. fabrication-heavy).
2. **Failure-mode stratification.** Every metric is reported per failure mode:
   `fabrication` (invented quote), `quote-mining` (real quote, doesn't entail),
   `number-swap` (figure/date mismatch). The headline `false-entail rate` is
   reported with a CI **per stratum**, not just aggregate.
3. **Adversarial slice.** At least one third of claims must be hard:
   contested / legal / causal / numeric. A held-out subset is labeled with the
   **full source** visible (not just the cited span) to measure span-selection
   bias (quote-mining), per PRD §8.

## Topic selection criteria
A candidate topic qualifies iff it:
- has **verifiable primary sources** (law text, filings, peer-reviewed, official docs);
- naturally produces **high-risk claims** (numbers/dates/legal/causal);
- contains at least one **known quote-mining trap** (a source with a qualifier/exception
  that a naive summary drops);
- is **time-bounded** (snapshot-stable enough to freeze sources).

## Human-label protocol (PRD §8)
- ≥2 **independent** labelers, **blind** to the system's verdict.
- Label unit = `(atomic_claim, span)`; 3-way `entails | neutral | contradicts`.
- Acceptance gate: **Cohen's κ ≥ 0.7**; disagreements adjudicated, logged.
- `n` sized to bound the per-stratum false-entail rate with a stated CI.
- A written rubric (`labels/RUBRIC.md`, TODO) defines each label + edge cases.

## Layout
```
bench/
  topics.json      # DRAFT candidate set (this commit) — needs external validation to lock
  baseline/        # insane-research baseline metrics on the frozen topics (M0 0.3)
  labels/          # human-labeled (atomic_claim, span) gold set + RUBRIC.md (M0 0.4)
```

> **Status:** `topics.json` is a **draft** illustrating the criteria/strata. It is
> NOT yet the locked, signed set — locking requires non-author/third-party
> validation per rule #1.
