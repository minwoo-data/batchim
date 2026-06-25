# Next-session handoff — investigate over-abstention & cost

Paste the block below into a fresh session.

---

You are picking up the **batchim (받침)** project at `C:\Users\user\projects\batchim`
(GitHub `minwoo-data/batchim`, branch `main`, working tree clean, all pushed).

**What batchim is:** a verification-gated deep-research plugin for Claude Code (fork of
`fivetaku/insane-research`). The pipeline:
`classify_risk → dedup/semantic/provenance (independence) → snapshot → isolated verifier →
entail_gate (code anchors: verbatim span-match + scale/unit numeric + polarity) →
decide.py (§6.7) → validate_ledger (sole joiner) → M2 panel (N=3, quote-mining) →
manifest/commit (signed, durable)`. Phase-7 gate = `eval_report.py`. Measurement tooling =
`bench/` (kappa, score_benchmark, freeze). 334 tests green across 20 files
(`for t in tests/test_*.py; do python "$t"; done`).

**What we've ALREADY measured:** false-entail (letting a WRONG claim through). On an informal
3-topic e2e it went 1/6 → 0/6 with the M2 panel (`bench/baseline/m1a_informal_smoke.md`).

**The gap to investigate THIS session — the under-examined failure mode:**

1. **Over-abstention / verified_recall** — does the gate reject TRUE claims too aggressively?
   We optimized against false-entail but barely tested false-NEGATIVE. A gate that abstains on
   everything has leak_rate 0 but is useless.
   - Build a CONTROL-HEAVY fixture: ~10–15 *genuinely-true, well-evidenced* high-risk claims
     (real topics: RFC specs, SEC filings, peer-reviewed numbers) with correct cited spans.
   - Run them through the gate (you can drive it manually like the smoke did, or via
     `bench/score_benchmark.py` with a gold set marking them control/should-verify).
   - Measure `verified_recall = verified ÷ should-be-verified`. Find WHICH step over-rejects:
     - numeric anchor too strict? (a claim quantity not in the proof span — `anchors._quantities`)
     - polarity false-positive? (`anchors.polarity_ok`)
     - independence requirement? (`decide.py` needs ≥2 distinct clusters incl ≥1 A/B)
     - panel quarantine on `no_consensus`? (`panel.py`)
   - Output: a verified_recall number + a ranked list of over-rejection causes + proposed fixes.

2. **Cost** — nobody adopts a research tool without a "$ / tokens per run" number.
   - Count LLM calls: 1 isolated verifier per cited (claim×source) ref + 3 panel lenses per
     verified-candidate. Model tokens/run as a function of #high-risk-claims and #sources.
   - Add a cost-estimate helper (extend `budget.py`; it already has the NFR-1 caps
     MAX_VERIFIER_CALLS=120 etc.) and surface a pre-launch estimate.
   - Sanity-check against the smoke runs.

3. **Then decide trims** based on findings (a separate critique lives in
   `docs/VS-INSANE-RESEARCH.md` and the chat history flagged: orchestrator.py + pipelines.py
   are ~830 LOC of inherited dead helpers; old PRD-v0.1/2/3 are doc sprawl).

**Constraints:** keep the 334-test suite green; commit per deliverable with the repo's
`feat/fix/docs(...)` style + the Co-Authored-By trailer; push to `main`. Don't over-build —
the meta-lesson is "prove the number before more engineering." Start by reading
`docs/M0-PLAN.md`, `bench/baseline/m1a_informal_smoke.md`, `anchors.py`, `decide.py`,
`bench/score_benchmark.py`.
