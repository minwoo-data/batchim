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
- [ ] `classify_risk.py` — deterministic risk + compound-claim atomization (regex/gazetteer/POS, NO LLM/network); target `risk_recall ≥ 0.98` on a fixture. (§6.1)
- [ ] `snapshot.py` — freeze source text + content hash. (§6.5)
- [ ] `entail_gate.py` — isolated verifier per `(atomic_claim, span+context, source)`; anchors: verbatim span-match (Appendix B) + numeric/date. (§6.3, App B)
- [ ] minimal `validate_ledger.py` decide-stage producing `verified_claims.json` via §6.7 (no signing yet).
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
