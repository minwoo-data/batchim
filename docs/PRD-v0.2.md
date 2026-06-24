# 받침 (Batchim) — PRD v0.2

> **In one sentence:** 받침 is a command you run inside Claude Code — `/batchim "<your research question>"` — that produces a cited research report in which **every high-risk claim is held back until a separate, isolated checker confirms the cited source text actually supports it.** Fewer confident-but-wrong AI answers, with a machine-readable audit trail.

| | |
|---|---|
| **Status** | Draft **v0.2** (revised after prism-all + triad-all dual-engine review; 16-agent convergence) |
| **Form factor** | Claude Code plugin (skill + deterministic code gates) |
| **Name** | **받침 (Batchim)** — locked (was provisional in v0.1) |
| **Lineage** | Fork & extension of `fivetaku/insane-research` (MIT) — attribution required |
| **MVP** | **M0 (fork green) + M1 (entailment gate)**. Panel voting (M2) and RAG retrieval (M3) are fast-followers. |
| **Author / Date** | Minwoo Park (minwoo-data) / 2026-06-23 |

### 5-minute summary
- **What:** an installable Claude Code plugin for deep research with a *verification gate*.
- **Who:** researchers/analysts who need citation-defensible reports (due diligence, competitive intel, regulated domains) and have been burned by confident-but-wrong AI summaries.
- **Why it's different:** other tools *ask* the model to be accurate; 받침 **mechanically checks** that each cited source entails its claim, in code, and **quarantines** anything it can't confirm.
- **How (high level):** research → collect sources (snapshotted) → an **isolated verifier** judges each (claim, evidence span) → a deterministic gate promotes only confirmed claims into the report; the rest go to an annex.
- **MVP ships:** `/batchim "<topic>"` → a report where every high-risk **verified** claim carries a stored, source-matched entailment proof.

---

## 0. Terminology (read first)

| Term | Plain meaning |
|---|---|
| **Entailment** | Does this source text actually support this claim? → `entails` / `neutral` / `contradicts`. |
| **NLI** | Natural Language Inference — the ML task of judging entailment. (v1 uses an LLM verifier, not a hosted NLI model — see D1.) |
| **RAG** | Retrieval-Augmented Generation — fetch the most relevant source passages before judging/writing. |
| **MCP** | Model Context Protocol — optional external tool servers (e.g. Firecrawl, Exa) the plugin uses if present. |
| **prism / ddaro / triad** | The author's existing in-house Claude Code tools we reuse: **prism** = multi-agent review panel; **ddaro** = parallel-agent rate-limit/throttle guard; **triad** = 3-lens convergence loop. |
| **Data-flow lock** | The architectural trick (inherited): synthesis may only use claims from `verified_claims.json`, and *only the gate produces that file* — so verification can't be skipped. |
| **Claim ledger** | `claim_ledger.jsonl` — one record per claim, author-owned (see §6.4 ownership). |
| **High-risk claim** | A claim whose error is costly: numbers/%, currency, dates, legal/financial/causal assertions. **Classified deterministically in code** (§6.1), not by the LLM. |

---

## 1. Background & Motivation

**The pain:** AI research tools sound authoritative but routinely attach a *real* citation to a claim the source doesn't actually support. The reader can't tell. That single failure mode — confident text over non-supporting evidence — is what 받침 exists to remove.

**Starting point.** We analyzed the strongest open example, `insane-research`, and adopt its best idea while fixing its two structural gaps.

### What insane-research gets right (we keep this)
- **Prompt orchestrates, code verifies** + the **data-flow lock**: synthesis consumes only gate-approved claims; only the gate writes that allowlist; a signature makes a pass tamper-evident.
- **Abstention by default** (unresolved/refuted quarantined to annex), A–E source grading, resumable `state.json`, deterministic eval scorer.

### The two structural gaps (our opening)
- **Gap A — the "code gate" trusts LLM-set booleans.** `classify_claim()` is deterministic, but its inputs (`conflicting`, `primary_source`, `counter_refuted`, `risk`) are filled freely by the LLM. The gate never checks the cited source's text actually entails the claim.
- **Gap B — "2 independent sources" = distinct domain count.** Syndicated/copied content across two domains counts as "independent," so cross-verification is fakeable.

### Honest framing of our fix (revised per review)
We do **not** claim "verification in code" in the strong sense — the entailment judgment is still produced by an LLM verifier (D1). What we *do* claim, precisely:

> **받침 computes claim status in code by aggregating the verdicts of an isolated verifier, anchored by mechanical checks (verbatim-span match, number/date/unit consistency, near-duplicate collapse), over frozen, signed evidence.**

That is strictly more rigorous than insane-research (which consumes the *author's* self-report), while not overstating determinism. The residual trust boundary (the verifier is an LLM) is stated openly in §12 and hedged by mechanical anchors (M1) and panel voting (M2).

---

## 2. Goals / Non-Goals

### Goals
- G1. Every **high-risk** claim in the report is promoted only after an **isolated** verifier returns `entails` from ≥2 *source-independent* sources, **and** the cited span is verbatim-present in the frozen source snapshot.
- G2. Preserve and strengthen the data-flow lock; sign the **frozen verdict + source artifacts** (not the regenerable claims) so a pass is tamper-evident and reproducible.
- G3. Beat insane-research on a **shared, pre-registered** benchmark using both internal metrics *and* human-labeled entailment precision/recall.
- G4. Ship as a low-friction Claude Code plugin (`/batchim "<topic>"`) with the same UX surface.

### Non-Goals (v1)
- NG1. **No long-running self-hosted model servers.** Ephemeral local scripts and optional MCP backends are allowed (clarified from v0.1).
- NG2. No hosted SaaS / web product. Local CLI demo + optional static report only.
- NG3. Batch sessions only (no streaming).
- NG4. Not a replacement for the web-search stack — we layer on top of WebSearch/WebFetch/MCP.

---

## 3. Usage Example (what the user sees)

```
> /batchim "Did the EU AI Act ban real-time biometric identification in public spaces?"

[batchim] scoping → planning → retrieving (snapshotting sources) → verifying → synthesizing

Report: RESEARCH/eu_ai_act_biometric_20260623/outputs/
  ✓ 14 high-risk claims verified (each with a source-matched quote)
  ⚠ 3 quarantined → see "Unresolved"   (e.g. exact effective date: sources disagree)
  ✗ 1 refuted → see "Refuted"          (a claim a credible source contradicted)
```

**The differentiator, concretely:** insane-research would mark *"the Act bans all real-time biometric ID"* **verified** because a blog says so. 받침 runs the isolated verifier against the cited text, finds the source says *"with law-enforcement exceptions,"* labels it `neutral` → the claim is **quarantined as unresolved**, not asserted in the body.

---

## 4. Differentiation

| | Generic deep-research bot | insane-research | **받침 (Batchim)** |
|---|---|---|---|
| Verification | Prompt asks LLM to "be accurate" | Deterministic gate over **LLM-set** booleans | Deterministic gate over **isolated-verifier verdicts + mechanical anchors** |
| Claim↔evidence | Implicit | `src_id` link, **unchecked** | Verifier verdict **+ verbatim-span match in frozen snapshot** |
| Independence | None | Distinct-domain count (fakeable) | Canonical-URL + near-dup collapse (M1) → semantic (M3) |
| Adversarial check | None | Single verify agent (strict mode only) | prism-style **panel votes** (M2) |
| Auditability | None | Source list | **Auditable ledger**: per-claim evidence cards, spans, hashes, verdicts, contradiction log |

**Moat (revised):** the methodology is copyable; the defensibility is **evidence** — a public, adversarial, third-party-labeled benchmark where 받침 measurably beats baselines on *human-judged* grounding, plus the auditable-ledger artifact users can inspect. We sell *"an auditable research ledger,"* not just *"less hallucination."*

---

## 5. Architecture Overview

```
batchim/
├── .claude-plugin/plugin.json
├── commands/batchim.md
└── skills/batchim-main/
    ├── SKILL.md                       # orchestration (prompt)
    ├── scripts/
    │   ├── classify_risk.py           # ★ deterministic high-risk classifier (§6.1)
    │   ├── snapshot.py                 # ★ freeze source text + content hash
    │   ├── entail_gate.py              # ★ runs isolated verifier; writes entailment_verdicts.jsonl + mechanical anchors
    │   ├── dedup.py                     # ★ M1: canonical-URL + simhash near-dup; M3: + semantic
    │   ├── validate_ledger.py          # SOLE joiner → verified_claims.json + signed manifest
    │   └── eval_report.py              # extended metrics (§9)
    ├── references/                      # contracts (inherited + edited)
    └── assets/templates/                # report templates
```

### Pipeline (artifact ownership is explicit)
```
1 Scope → 2 Plan → 3 Retrieve(+snapshot.py freeze) → 3.5 dedup.py(independence) → 4 Triangulate
                                                                                       │
                                          author writes claim_ledger.jsonl (author-owned, immutable after write)
                                                                                       ▼
                              4.5 entail_gate.py  (MVP):
                                 classify_risk → for each high-risk claim × cited span:
                                   isolated verifier → {entails|neutral|contradicts}
                                   + verbatim-span match against frozen snapshot
                                   + numeric/date/unit consistency check
                                 → writes entailment_verdicts.jsonl  (gate-owned)
                                 (M2: prism panel votes refine contradicts/conflicting — NOT in M1)
                                                                                       ▼
                              validate_ledger.py  (SOLE joiner): ledger ⋈ verdicts ⋈ sources
                                 → verified_claims.json | unresolved | refuted
                                 → signed manifest in state.json (§6.5)
                                                                                       ▼
5 Synthesis (verified-only) → 6 QA → 7 Output ── eval_report.py HARD gate (§6.6)
```

### How the verifier works (concrete, addresses isolation + span integrity)
Per high-risk claim, per cited span, `entail_gate.py` **spawns a fresh isolated subagent** (Task/Agent) receiving **only** `{claim_text, source_snapshot_text}` — no research history, no author rationale (satisfies G1 isolation). It returns structured output:
```json
{ "claim_id":"clm_001", "source_id":"src_003",
  "label":"entails|neutral|contradicts",
  "evidence_span":"verbatim quote from the source",
  "note":"1-line rationale" }
```
`entail_gate.py` then applies **mechanical anchors** (these are real code checks, the core upgrade over Gap A):
1. **Verbatim-span match** — `evidence_span` must appear in the frozen `source_snapshot` (whitespace-normalized). No match ⇒ verdict rejected (treated as `neutral`, claim cannot reach verified).
2. **Numeric/date/unit check** — for numeric/date/legal claims, extracted figures in the span must be consistent with the claim. Mismatch ⇒ `neutral`.
3. **Independence** — `entails` verdicts counted only after `dedup.py` collapse (§6.2).

---

## 6. Functional Requirements

### 6.1 Deterministic risk classification (fixes Gap-A residual)
- FR-R0. `classify_risk.py` computes `risk:"high"` from the claim text in code: presence of number/%/currency, date, or (named-entity + legal/financial/causal verb). The author LLM **may** suggest risk, but the gate **recomputes and overrides**; low-risk-mislabeling cannot route a numeric/legal claim around the gate.

### 6.2 Independence (closes Gap B in MVP)
- FR-I0. **M1 independence** = distinct-source after `dedup.py` collapse: canonical-URL normalization + normalized-text simhash/shingle overlap + publication-time clustering. This ships in **M1** (not M3).
- FR-I1. **M3 upgrade** = semantic embedding near-dup, as an enhancement; it must **not** collapse genuinely independent outlets reporting a common fact — distinguish *content* near-dup from *provenance* dependence (shared wire/citation chain).

### 6.3 Entailment gate ★ MVP (M1)
- FR-E1. For every high-risk claim, run the isolated verifier on each cited span; persist a terminal verdict (`done|failed`) per span. **No span may remain `pending`** at finalize (else exit 2).
- FR-E2. Apply mechanical anchors (verbatim match, numeric check). A span whose quote isn't found in the snapshot is rejected.
- FR-E3. **Canonical `verified` rule (single source of truth — Decision Table §6.7).**
- FR-E4. **Fail-closed:** any high-risk claim lacking a terminal computed verdict, or whose span fails the anchor, defaults to **`unresolved`** — never inherits an author boolean.

### 6.4 Artifact ownership & schema (addresses architect lens)
- FR-A1. `claim_ledger.jsonl` is **author-owned and immutable after write**. Author fields live under `claimed_*`.
- FR-A2. `entail_gate.py` writes a **separate** `entailment_verdicts.jsonl` (gate-owned, `computed_*`). It does **not** mutate the ledger.
- FR-A3. `validate_ledger.py` is the **sole** component that joins ledger ⋈ verdicts ⋈ sources and emits `verified_claims.json`. For high-risk claims it reads **only `computed_*`**.
- FR-A4. Every artifact carries `schema_version`. Unknown labels / malformed records are quarantined (never silently `neutral`).
- FR-A5. **Referential integrity** (fail-closed, exit 2): every `source_id` in ledger/verdicts must resolve in `sources.jsonl`.

### 6.5 Tamper-evidence (fixes determinism contradiction)
- FR-S1. Sign a **manifest** over: `entailment_verdicts.jsonl`, frozen `sources/` snapshots (+ content hashes), `verified_claims.json`, gate version, schema versions. Store sha256 in `state.json`.
- FR-S2. **Determinism is scoped** to `validate_ledger.py`'s arithmetic over **frozen verdicts** — not over verifier generation. On resume, **replay frozen verdicts**; re-query the verifier only for spans with no frozen verdict (NFR-3).

### 6.6 Exit-code contract (fixes crash-vs-zero conflation)
- FR-X1. Gate exit codes: **0** = ran, allowlist written; **1** = ran, 0 verified (legitimate abstention); **2** = error (corruption / orphan id / incomplete verdicts). Orchestrator **blocks synthesis on exit 2**, distinct from exit 1.
- FR-X2. `eval_report.py` is a **hard gate** at Phase 7: `missing_entailment_proof_rate > 0` OR any dangling citation ⇒ FAIL (exit 2) ⇒ output blocked.

### 6.7 Canonical "verified" Decision Table (single source of truth)
A high-risk claim is:
- **refuted** — if ≥1 `contradicts` from a **credible** source (A/B grade) that is not refuted by the M2 panel (in M1, any A/B `contradicts` ⇒ refuted; no override exists pre-M2).
- **verified** — else if **all**: (a) ≥2 **independent** (§6.2) `entails`; (b) every cited span verbatim-matched in snapshot; (c) numeric/date checks pass; (d) ≥1 source is A/B grade.
- **unresolved** — otherwise (incl. <2 independent, only `neutral`, failed anchor, missing verdict, unresolved conflict).

Non-high-risk claims follow the inherited path (cite-and-write); only high-risk claims pass this gate.

### 6.8 prism panel (M2) & RAG (M3)
- FR-P1. M2: for high-risk/contested claims, an **N=3** prism panel (refute / source-quality / numeric-consistency) decides `contradicts`/`conflicting` by **majority (≥2 of 3)**; ties ⇒ quarantine (abstain, never majority-rules). Disagreement triggers triad-style convergence, **hard cap 3 rounds**.
- FR-P2. Throttle **all** verifier/panel fan-out (M1 included) to 2–3 concurrent with liveness check + sequential fallback (ddaro guard); never a 16-wide fan-out. Shared per-session **budget** (FR-N1).
- FR-P3. M2 panel verdicts and M1 single-verifier verdicts merge by a stated precedence: **panel overrides single verifier** for `contradicts`/`conflicting`; both recorded with `producer`.
- FR-R3. M3: embeddings + cross-encoder rerank + hybrid (BM25+dense) retrieval + query expansion. Embedding backend = committed local script default, MCP if present; **no embedding backend ⇒ dedup degrades to lexical (FR-I0) and independence flagged best-effort** (NFR-5).

### 6.9 Inherited (keep, adapt)
- Data-flow lock; abstention; resumable `state.json`; A–E grading; templates; `/batchim`, `resume`, `status`, structured-JSON query.

---

## 7. Non-Functional Requirements
- **NFR-1 Cost (concrete).** Per-session caps: `max_verified_calls` (default e.g. 120), `max_spans_per_claim` (default 3). Estimated call count shown in `/batchim status` before launch. **On cap-exhaustion: hard stop, mark remaining high-risk claims `unresolved`, surface a coverage warning** — never silently shrink the verified set.
- **NFR-2 Reliability.** Per-call timeout; on timeout mark span `failed`, retry once foreground, then quarantine. No silent background death (liveness checks).
- **NFR-3 Determinism (scoped).** `validate_ledger.py` output + signature are reproducible **given the frozen verdict/snapshot set** (FR-S2). Verifier generation is not claimed deterministic.
- **NFR-4 Concurrency safety.** Per-session **lockfile (PID + heartbeat)** + atomic temp-then-rename writes; stale-lock recovery.
- **NFR-5 Graceful degradation.** Missing MCP (Firecrawl/Exa) ⇒ WebSearch/WebFetch; missing embedding backend ⇒ lexical dedup; degradations recorded in `state.json`.
- **NFR-6 Privacy.** Research artifacts stay local. Stated data egress: search queries + (claim, span) pairs go to the configured search/LLM providers; nothing else leaves the machine; no telemetry.

---

## 8. MVP Scope & Phasing

| Milestone | Scope | Done when |
|---|---|---|
| **M0** Fork & baseline | Fork insane-research → rebrand 받침; run end-to-end unchanged; **freeze benchmark + baseline** | `/batchim "<topic>"` produces a report; **5 benchmark topics chosen, insane-research baseline numbers recorded**, human-labeled entailment set started (Q-bench) |
| **M1** Entailment gate ★ | FR-R0, FR-I0, FR-E1–E4, FR-A1–A5, FR-S1–S2, FR-X1–X2, NFR-1/2/3/4 | `missing_entailment_proof_rate=0`; every verified claim has a span-matched proof; `entailment_precision` reported vs human set; throttle + budget enforced |
| **M2** prism panel | FR-P1–P3 | booleans decided by votes; A/B beats M1 on `leak_rate` by a pre-registered margin (n=5) |
| **M3** RAG quality | FR-I1, FR-R3 | semantic dedup changes independence outcomes; rerank improves `verified_recall` without raising `leak_rate` |

**MVP = M0 + M1.** Benchmark/baseline is an **M0 deliverable**, not an open question.

---

## 9. Success Metrics (internal + external)
**Structural (must hold, gate-enforced):**
- `missing_entailment_proof_rate = 0` *(renamed from v0.1's misleading `ungrounded_verified_rate`; means "every verified claim has a span-matched stored proof")*.
- `citation_resolution_rate = 100%`; `span_match_rate = 100%` for verified claims.

**Correctness (external, the real bar):**
- `entailment_precision` / `entailment_recall` vs the **human-labeled** set (false-entail rate is the headline number).

**Health (anti-gaming):**
- `abstention_rate` / `quarantine_rate` — **capped**; a report that verifies 6% of its claims is a *failure* even at leak 0.
- `leak_rate` (inherited) lower than insane-research baseline by a pre-registered margin.

A/B: gate-on vs gate-off, and 받침 vs insane-research, on the 5 frozen topics; metrics & thresholds **pre-registered before tuning**.

---

## 10. Key Tech Decisions
- **D1.** Entailment engine = **isolated structured-output verifier subagent** + mechanical anchors (not hosted NLI). A local NLI/cross-encoder is an **M3 option**, not a v1 dependency.
- **D2.** Embeddings (M3): committed local script default; MCP if present; per-session disposable index; lexical fallback if absent.
- **D3.** Reuse prism (panel) / ddaro (throttle) / triad (convergence) patterns; don't reinvent.
- **D4.** Artifact schemas are a **versioned superset** of insane-research, with explicit `claimed_*` / `computed_*` namespaces. (See Appendix A.)

---

## 11. Open Questions / Decisions Needed
- ~~Q1 Name~~ → **Resolved: 받침 (Batchim).**
- ~~Q5 Benchmark~~ → **Promoted to M0 deliverable** (5 topics + human labels + baseline).
- Q2. Distribution: standalone repo **and** list in the author's `haroom_plugins` marketplace (recommended).
- Q3. Entailment granularity in M1: claim-vs-cited-snippet **with surrounding context window** (decided), full-source-chunk retrieval deferred to M3.
- Q4. Which inherited reference docs to keep verbatim vs rewrite for the new gate semantics (track in M0).
- Q6. Should the verifier be allowed an **independent retrieval** pass (search for *contradicting* evidence beyond the author's span)? Strong for rigor; cost/scope tradeoff → evaluate in M2.

---

## 12. Risks
- R1. **Residual trust in the verifier (an LLM).** Mitigation: mechanical anchors (M1) + heterogeneous panel (M2) + human-labeled precision metric; honest framing (§1).
- R2. **Correlated model error** in same-model panels. Mitigation: distinct lenses + abstain-on-split (not majority-rules) + require contrary-evidence search; ship panel only if it beats single-verifier on human labels.
- R3. **Quote-mining / context bias** (verifier sees author-picked span). Mitigation: include surrounding context; M2 contradiction search; Q6.
- R4. **Cost blow-up.** Mitigation: high-risk-only + deterministic risk + budget caps + cap-exhaustion behavior (NFR-1).
- R5. **Rate limits.** Mitigation: throttle from M1 (FR-P2).
- R6. **Stale/changed web content** breaking reproducibility & span audit. Mitigation: source snapshots + hashes (FR-S1).
- R7. **Scope creep across 3 axes.** Mitigation: strict phasing; MVP is entailment-only.
- R8. **License/attribution.** Mitigation: preserve NOTICE; correct upstream link (§13).

---

## 13. Attribution
Derivative work of **`fivetaku/insane-research`** (distributed via the `fivetaku/gptaku_plugins` marketplace; MIT). 받침 retains the data-flow-lock architecture and eval methodology, and adds: deterministic risk classification, source snapshotting, the entailment gate with mechanical anchors, explicit artifact-ownership boundaries, semantic/lexical dedup, and a prism-style verification panel. License: MIT, with a NOTICE crediting the upstream author.

---

## Appendix A — Artifact Schemas (to finalize in M0)
```jsonc
// sources.jsonl (author + snapshot)
{ "id":"src_001","url":"…","domain":"…","quality_rating":"A|B|C|D|E",
  "fetched_at":"…","content_hash":"sha256:…","snapshot_path":"…","schema_version":1 }

// claim_ledger.jsonl  (AUTHOR-OWNED, immutable; claimed_* only)
{ "claim_id":"clm_001","text":"…","claimed_risk":"high|normal",
  "claimed_source_ids":["src_001","src_003"],"schema_version":1 }

// entailment_verdicts.jsonl  (GATE-OWNED; computed_*)
{ "claim_id":"clm_001","source_id":"src_003","producer":"verifier|panel",
  "label":"entails|neutral|contradicts","evidence_span":"…",
  "span_matched":true,"numeric_ok":true,"schema_version":1 }

// verified_claims.json  (validate_ledger output: computed status only)
{ "claim_id":"clm_001","status":"verified|unresolved|refuted",
  "independent_entails":2,"proof_source_ids":["src_001","src_003"] }
```
