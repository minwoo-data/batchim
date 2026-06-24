# M0 Plan — 받침 (Batchim)

Source of truth: [`PRD.md`](PRD.md) v0.4. MVP = **M0 + M1 + M2** (panel is in the MVP).

## M0 — Fork & baseline (current)

| # | Deliverable | PRD ref | Status |
|---|---|---|---|
| 0.1 | Fork `fivetaku/insane-research` → rebrand 받침 (plugin.json, command `/batchim`, skill `batchim-main`, NOTICE) | §13 | ✅ done (this commit) |
| 0.2 | Freeze **benchmark**: 5+ topics, third-party/criteria-selected (not author cherry-pick), incl. an adversarial slice (contested/legal/causal/numeric) | §8, §9, R7 | ☐ todo → `bench/topics.json` |
| 0.3 | Record **insane-research baseline** metrics on the frozen topics (leak_rate, citation, false-entail by human label) | §8 M0, §9 | ☐ todo → `bench/baseline/` |
| 0.4 | Build **human-label set**: ≥2 independent labelers, blind, rubric, unit = `(atomic_claim, span)`, **κ ≥ 0.7**, `n` sized for false-entail CI, full-source adversarial subset | §8 protocol | ☐ todo → `bench/labels/` |
| 0.5 | **Sign** benchmark topic-set hash + threshold vector + human-label-set hash (frozen) | FR-S1 | ☐ todo |

## M1a — Vertical slice (FIRST, measures the core experiment)
Goal: **measure false-entail rate vs human labels** before any durability machinery.
- [x] `classify_risk.py` — deterministic risk + compound-claim atomization (regex/gazetteer/POS, NO LLM/network); risk_recall ≥ 0.98 on fixture; gazetteer_hash pinned. (§6.1) ✅ 9e9feb6
- [x] `snapshot.py` — freeze source text + content hash. (§6.5) ✅ f9d1a61
- [x] `entail_gate.py` — code half done: join raw verifier verdicts → anchors (span-match + numeric) → bound `entailment_verdicts.jsonl`. (§6.3, App B) ✅ e9ca82a · SKILL.md Phase 4.5 wires the isolated-verifier subagent spawn → `raw_verdicts.jsonl` ✅
- [x] minimal `validate_ledger.py` decide-stage producing `verified_claims.json` via §6.7 (no signing yet). ✅ e93295b — SOLE joiner; FR-A5 binding + FR-X3 coverage; M1b adds signing.
- [ ] **Experiment:** run M1a on the M0 benchmark, compute false-entail rate stratified by failure-mode. **Gate:** is M1a meaningfully better than baseline on fabrication/number? (quote-mining expected flat until M2.)

## M1b — Durability
- [ ] Artifact ownership + schemas (Appendix A), referential/binding integrity (FR-A1–A5).
- [ ] Input-closure manifest + single-rename commit + cross-version replay (FR-S1–S4).
- [ ] Exit taxonomy + coverage invariant + body re-classification backstop (FR-X1–X3, FR-R1).
- [ ] `dedup.py` → frozen `independence_partition.json` (FR-I0). Throttle/budget (FR-P2, NFR-1).
- [ ] Golden fixtures for **every** §6.7 branch (D5); Appendix B normalization fixture corpus.

## M2 — Panel (completes MVP)
- [ ] `panel.py` — N=3 prompt-diverse lenses, 2-of-3 consensus, producer-aware aggregation (FR-P1/P3).
- [ ] **Quote-mining defense:** panel gates `verified` (§6.7-4b).
- [ ] **Launch gate:** human-precision stratified by failure-mode beats insane-research on false-entail by the pre-registered margin; `verified_recall` gate honored (§9).

## M3 — RAG (post-MVP)
- [ ] Embeddings + rerank + hybrid + semantic dedup (FR-I1, FR-R3).

## E2E smoke findings (t6 HTTP/3·TLS1.3 — gate ran end-to-end; 3/3 correct: c1 verified, number-swap + fabrication both blocked)
- [x] **dedup bug (fixed):** `dedup.py` read `snippet`/`title` (absent in Appendix A schema), so empty simhash=0 collapsed distinct sources into one cluster (independence loss). Now reads `text` + guards empty-token sources to canonical-URL-only. +regression tests.
- [ ] **numeric anchor over-strict (open):** `numeric_ok` counts identifier/ordinal integers ("QUIC version **1**", "HTTP/3") as quantities a proof span must contain → false anchor failure → verified_recall loss. Fail-closed (safe; no false-entail), but needs a TDD refinement to distinguish identifiers from quantities (e.g. ignore bare single-digit integers in identifier context; keep decimals/years/%/currency/multi-digit). Affects FR-E2/§9 `verified_recall`.

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
