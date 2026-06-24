# M0 Plan — 받침 (Batchim)

Source of truth: [`PRD.md`](PRD.md) v0.4. MVP = **M0 + M1 + M2** (panel is in the MVP).

## M0 — Fork & baseline (current)

| # | Deliverable | PRD ref | Status |
|---|---|---|---|
| 0.1 | Fork `fivetaku/insane-research` → rebrand 받침 (plugin.json, command `/batchim`, skill `batchim-main`, NOTICE) | §13 | ✅ done (this commit) |
| 0.2 | Freeze **benchmark**: 5+ topics, third-party/criteria-selected (not author cherry-pick), incl. an adversarial slice (contested/legal/causal/numeric) | §8, §9, R7 | ☐ todo → `bench/topics.json` |
| 0.3 | Record **insane-research baseline** metrics on the frozen topics (leak_rate, citation, false-entail by human label) | §8 M0, §9 | ☐ todo → `bench/baseline/` |
| 0.4 | Build **human-label set**: ≥2 independent labelers, blind, rubric, unit = `(atomic_claim, span)`, **κ ≥ 0.7**, `n` sized for false-entail CI, full-source adversarial subset | §8 protocol | **Tooling ready** (`bench/kappa.py` κ-gate, `bench/score_benchmark.py` §9 metrics, `RUBRIC.md`). ☐ real labelers (human step). |
| 0.5 | **Sign** benchmark topic-set hash + threshold vector + human-label-set hash (frozen) | FR-S1 | **Done** (`bench/freeze.py` — signs topic/threshold/label hashes; `verify` detects post-freeze drift). ☐ run once topics+labels locked. |

## M1a — Vertical slice (FIRST, measures the core experiment)
Goal: **measure false-entail rate vs human labels** before any durability machinery.
- [x] `classify_risk.py` — deterministic risk + compound-claim atomization (regex/gazetteer/POS, NO LLM/network); risk_recall ≥ 0.98 on fixture; gazetteer_hash pinned. (§6.1) ✅ 9e9feb6
- [x] `snapshot.py` — freeze source text + content hash. (§6.5) ✅ f9d1a61
- [x] `entail_gate.py` — code half done: join raw verifier verdicts → anchors (span-match + numeric) → bound `entailment_verdicts.jsonl`. (§6.3, App B) ✅ e9ca82a · SKILL.md Phase 4.5 wires the isolated-verifier subagent spawn → `raw_verdicts.jsonl` ✅
- [x] minimal `validate_ledger.py` decide-stage producing `verified_claims.json` via §6.7 (no signing yet). ✅ e93295b — SOLE joiner; FR-A5 binding + FR-X3 coverage; M1b adds signing.
- [ ] **Experiment:** run M1a on the M0 benchmark, compute false-entail rate stratified by failure-mode. **Gate:** is M1a meaningfully better than baseline on fabrication/number? (quote-mining expected flat until M2.)

## M1b — Durability
- [~] Artifact ownership + schemas (Appendix A), referential/binding integrity (FR-A1–A5). **FR-A5 binding done** (validate_ledger: snapshot_hash/claim_text_hash/grade-copy → exit 2).
- [~] Input-closure manifest + single-rename commit + cross-version replay (FR-S1–S4). **FR-S1 signed manifest done** (`manifest.py`: content-addressed run_id, sha256 over input-closure + code versions + enabled_producers; `verify()` detects tamper/skip). ☐ FR-S2 replay, ☐ FR-S3 single-rename `CURRENT` commit, ☐ FR-S4 superseded_by gate.
- [~] Exit taxonomy + coverage invariant + body re-classification backstop (FR-X1–X3, FR-R1). **FR-X1/X3 done** (exit 0/1/2 + coverage invariant in validate_ledger). ☐ FR-R1 Phase-6 body backstop.
- [x] `dedup.py` → frozen `independence_partition.json` (FR-I0). ☐ Throttle/budget (FR-P2, NFR-1).
- [~] Golden fixtures for **every** §6.7 branch (D5) — `test_gate_core` covers all branches. ☐ Appendix B normalization fixture corpus.

## M2 — Panel (completes MVP)
- [x] `panel.py` — N=3 prompt-diverse lenses (refute/source_quality/numeric_consistency), 2-of-3 consensus, quarantine on split/missing/failed (FR-P1). validate_ledger auto-enables M2 from `panel_consensus.jsonl`; verified requires panel consensus `entails` (§6.7-4b). SKILL.md Phase 4.6 wires the lens subagents. ✅
- [x] **Quote-mining defense — demonstrated:** on the informal 3-topic smoke, the panel drove the hard quote-mine from a false-entail to quarantined → **false-entail 1/6 → 0/6, false-negative 0/6** (controls stayed verified). refute lens cited EU AI Act Art 5(1)(h) exceptions. See `bench/baseline/m1a_informal_smoke.md`.
- [ ] producer-aware supersession rows in `entailment_verdicts.jsonl` (FR-P3 append-only/supersedes) — M2b/durability; M2 uses a claim-level `panel_consensus.jsonl`.
- [ ] **Launch gate:** human-precision stratified by failure-mode beats insane-research on false-entail by the pre-registered margin; `verified_recall` gate honored (§9). (needs M0 human labels.)

## M3 — RAG (post-MVP)
- [ ] Embeddings + rerank + hybrid + semantic dedup (FR-I1, FR-R3).

## E2E smoke findings (t6 HTTP/3·TLS1.3 — gate ran end-to-end; 3/3 correct: c1 verified, number-swap + fabrication both blocked)
- [x] **dedup bug (fixed):** `dedup.py` read `snippet`/`title` (absent in Appendix A schema), so empty simhash=0 collapsed distinct sources into one cluster (independence loss). Now reads `text` + guards empty-token sources to canonical-URL-only. +regression tests.
- [x] **numeric anchor over-strict (fixed):** `numeric_ok` counted identifier/ordinal integers ("QUIC version **1**", "HTTP/3", "Section 12", "RFC 9114") as required quantities → false anchor failure → verified_recall loss. Now `_salient_nums` keeps only quantities (decimals/years/unit·%·currency-adjacent/multi-digit-non-identifier) and drops identifier-context + bare single-digit integers; span side still matches against all numbers so swaps (1.2 vs 1.3) are still caught. Verified on the t6 e2e: the original "QUIC version 1 …" claim now anchors + verifies without editing the claim. (FR-E2/§9 `verified_recall`.)

## Open decisions (carry from PRD §11)
- Q2 distribution (standalone repo + list in `haroom_plugins`), Q4 inherited-doc rewrite scope, Q6 verifier independent contrary-retrieval as an M2 lens.

## Layout
```
batchim/
  .claude-plugin/plugin.json   commands/batchim.md
  skills/batchim-main/{SKILL.md, scripts/, references/, assets/}
  skills/batchim-query/
  bench/        # M0: topics.json, baseline/, labels/   (to create)
  docs/         # PRD + review provenance + this plan
```
