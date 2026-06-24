# Changelog — 받침 (Batchim)

## [0.2.0] — unreleased (MVP gate built)
Forked from `fivetaku/insane-research` (MIT), rebranded 받침. The verification
core is new. 228 tests across 16 files. Formal human labeling still pending.

**M1 — entailment gate**
- `classify_risk` deterministic high-risk classifier + compound-claim atomization
  (regex/gazetteer, no LLM) + gazetteer hash.
- `snapshot` source freeze + content hash; `anchors` verbatim span-match + numeric
  (identifier-aware) consistency; `entail_gate` isolated-verifier join + anchors.
- `decide` §6.7 decision algorithm; `validate_ledger` sole joiner → verified_claims.
- `dedup` canonical-URL + simhash independence partition (FR-I0).

**M2 — panel (in MVP)**
- `panel` N=3 prompt-diverse lenses (refute / source_quality / numeric_consistency),
  2-of-3 consensus; gates `verified` (§6.7-4b). Closes quote-mining: informal
  e2e false-entail 1/6 → 0/6 with no control regression.

**M1b — durability**
- `manifest` signed input-closure + content-addressed run_id (FR-S1);
  `commit` single-rename `CURRENT` commit + byte-verified read (FR-S3);
  `replay` frozen/requery/tamper planner + cross-version guard (FR-S2);
  publish gate for superseded runs (FR-S4); `backstop` Phase-6 body re-classify
  (FR-R1); `budget` reserve-before-dispatch throttle (FR-P2).
- `eval_report` realigned to the new schema as the §9 Phase-7 hard gate.

**M0 — measurement infra** (real labelers pending)
- `bench/kappa` Cohen's κ gate (≥0.7), `bench/score_benchmark` false-entail /
  precision / recall vs human gold (via §6.7), `bench/freeze` pre-registration
  signing, `labels/RUBRIC.md`.

**M3 — post-MVP**
- `semantic` embedding-based independence (paraphrase syndication; FR-I1);
  `retrieval` hybrid BM25+embedding + rerank + query expansion (FR-R3). Both with
  deterministic offline fallbacks + pluggable real backends (NFR-5).

Bugs found & fixed by the e2e measurement: dedup empty-text cluster collapse,
numeric anchor identifier over-strictness, `ban/bans` gazetteer miss.
