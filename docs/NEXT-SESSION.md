# Next-session handoff — after over-abstention & cost session

Paste the block below into a fresh session.

---

You are picking up the **batchim (받침)** project at `C:\Users\user\projects\batchim`
(GitHub `minwoo-data/batchim`, branch `main`, working tree clean, all pushed).

**What batchim is:** a verification-gated deep-research plugin for Claude Code (fork of
`fivetaku/insane-research`). The pipeline:
`classify_risk → dedup/semantic/provenance (independence) → snapshot → isolated verifier →
entail_gate (code anchors: verbatim span-match + scale/unit numeric + polarity) →
decide.py (§6.7) → validate_ledger (sole joiner) → M2 panel (N=3, quote-mining) →
manifest/commit (signed)`. Phase-7 gate = `eval_report.py`. Measurement = `bench/`.
**21 test files / 377 assertions green** (`for t in tests/test_*.py; do python "$t"; done`).

## What the LAST session measured & shipped (read these first)
1. **`bench/baseline/control_recall.md` + `bench/verified_recall.py` + `bench/control/control_claims.jsonl`**
   — the over-abstention measurement (mirror of false-entail). Drove a control-heavy
   fixture of TRUE high-risk claims (RFC/SEC/peer-reviewed) through the REAL
   anchors+decide. **Finding: headline `verified_recall` was 0.667.** Root cause = the
   numeric anchor treated version/identifier numbers ("TLS 1.3", "OAuth 2.0", "RFC 1918"
   read as a year) as REQUIRED quantities.
   **Fix (anchors.py):** unit-less decimals → a `ver` class that is CONFLICT-only in
   `numeric_ok` (fails only on a DIFFERENT version in the span, not on omission);
   identifier context now drops year-form numbers. Measured units (pct/mag/year) keep
   omission-fail, so number/scale/percent swaps are still caught. **Result: 0.667 → 1.000**,
   zero false-entail regression (swap test `test_gate_core :71` still green).
2. **`budget.py` cost model** — `estimate_run`/`estimate_calls`/`estimate_tokens`/
   `estimate_cost`/`format_estimate` + CLI. verifier = 1 per cited ref; panel = 3 lenses
   per candidate; honors NFR-1 caps with a `[DEGRADED]` flag. Sanity-checked vs the smoke:
   6 claims/~10 refs/3 candidates ≈ **19 calls / ~43.6k tokens**. SKILL.md Phase 4.5 prints
   it pre-fan-out. Pricing is parameterized (`--price-in/--price-out`), not baked in.
3. **`docs/TRIM-DECISION.md`** — removed 830 LOC of unused, untested, fork-inherited
   `orchestrator.py`/`pipelines.py` (the latter held a SHADOW §6.7 status classifier that
   threatened the sole-joiner invariant) + 3 stale PRD snapshots. SKILL.md references rehomed.

## The open gaps THIS session should pick from
1. **The one cheap recall win still on the table:** `control_recall.md` flags **panel-lens
   retry before quarantine** — when a single lens fails/abstains, the claim is quarantined
   (`panel:no_consensus`) even when true. Retrying the failed lens once (separate budget)
   is precision-safe and recovers recall. Wire it in `panel.py` + SKILL.md Phase 4.6, with
   a test. (The other over-abstentions — independence ≥2 clusters, A/B grade floor, rounding,
   distributed-negation polarity — are deliberate §6.7 conservatism; do NOT loosen without a
   measured false-entail cost on the signed benchmark. See the trade-off table.)
2. **Still the biggest unmet dependency:** the **signed M0 benchmark** (`docs/M0-PLAN.md`
   items 0.2–0.5) needs REAL κ≥0.7 human labels. Every number so far (false-entail 1/6→0/6,
   verified_recall 0.667→1.0) is on INFORMAL author-known-answer sets. The launch gate (§9)
   is blocked on this human step. Tooling is ready (`bench/kappa.py`, `score_benchmark.py`,
   `freeze.py`); it needs labelers, not code.
3. **Optional:** a rounding tolerance for the numeric anchor (`$130.5B` vs exact `$130,497M`
   is currently flagged — defensible but strict). Measure the false-entail cost of a ±0.5%
   same-scale tolerance before adding it. `d_nvda_rounded` in the control fixture is the probe.

**Constraints:** keep the suite green; commit per deliverable with `feat/fix/docs(...)` +
the Co-Authored-By trailer; push to `main`. "Prove the number before more engineering."
Start by reading `bench/baseline/control_recall.md`, `bench/verified_recall.py`, `anchors.py`
(the `_quantities`/`numeric_ok` ver-class logic), `panel.py`, `decide.py`.
