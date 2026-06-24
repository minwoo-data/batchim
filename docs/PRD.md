# 받침 (Batchim) — PRD v0.4

> **In one sentence:** 받침 is a command you run inside Claude Code — `/batchim "<question>"` — where an **isolated model judges whether each citation supports its claim, a panel of independent lenses cross-checks the risky ones, and code mechanically enforces that the quoted text really exists and the numbers/dates line up** — quarantining anything that fails. Fewer confident-but-wrong AI answers, with a machine-readable audit trail.

| | |
|---|---|
| **Status** | Draft **v0.4** — build-ready target (after 3 dual-engine review rounds, prism-all + triad-all) |
| **Form factor** | Claude Code plugin (skill + deterministic code gates) |
| **Name** | **받침 (Batchim)** — locked. *받침* = the final consonant that **supports** a Korean syllable; here, the evidence that must support every claim. |
| **Lineage** | Fork & extension of `fivetaku/insane-research` (MIT). |
| **MVP** | **M0 + M1 + M2** — the panel is *in* the MVP, because the headline failure mode (quote-mining) is defended by the panel, not by M1's anchors alone. M3 (RAG) is the post-MVP fast-follower. |
| **Author / Date** | Minwoo Park (minwoo-data) / 2026-06-23 |

### 5-minute summary
- **What:** an installable Claude Code plugin for deep research with a *verification gate*.
- **Who:** researchers/analysts who need citation-defensible reports and have been burned by confident-but-wrong AI summaries.
- **Why it's different:** other tools *ask* the model to be accurate. 받침 (1) has an **isolated model** judge each citation, (2) runs a **panel of independent lenses** on risky claims to catch *quote-mining* (a real quote that doesn't actually support the claim), and (3) **code mechanically enforces** that the quote exists and numbers match — quarantining what it can't confirm.
- **Scope honesty:** the gate applies to **high-risk claims only** (numbers, dates, money, legal/causal). Lower-risk claims are cited (and citation-resolved) but not entailment-gated in v1. The entailment *judgment* is made by LLMs (isolated + panel), not a hosted NLI model; **code** guarantees the quote is real and numbers align, and that the whole pass is signed and reproducible. The defensible claim is *"an auditable, fail-closed, panel-checked entailment gate,"* not *"truth proven in code."*
- **MVP ships:** `/batchim "<topic>"` → a report where every **high-risk verified** claim carries a stored, source-matched, panel-confirmed entailment proof, plus an auditable ledger.

---

## 0. Terminology

| Term | Plain meaning |
|---|---|
| **Entailment** | Does this source text support this claim? → `entails` / `neutral` / `contradicts`. |
| **NLI** | The ML task of judging entailment. v1 uses isolated LLM verifiers + a panel, not a hosted NLI model (D1). |
| **Isolated verifier** | A fresh Claude subagent given **only** `(claim, cited span + fixed context window, source text)` — no research history — so it can't be biased by the author's reasoning. |
| **Panel (M2)** | N=3 prompt-diverse lenses (refute / source-quality / numeric-consistency) that cross-check a risky claim; 2-of-3 consensus required (§6.8). *Prompt-diverse, model-diverse where available — see R4: not fully independent.* |
| **Mechanical anchor** | A **code** check around the LLM verdict: (1) `evidence_span` exists verbatim in the frozen source; (2) numbers/dates/units match the claim. Anchors guard against *fabricated quotes / number swaps* — not, by themselves, quote-mining (that's the panel's job). |
| **Quote-mining** | Citing a real, verbatim quote that is locally true but does not entail the broader claim (the EU-AI-Act "with exceptions" case, §3). The dominant false-entail mode; defended by the panel + human-precision metric. |
| **RAG / MCP** | Retrieval-augmented generation / optional external tool servers (Firecrawl, Exa). |
| **prism / ddaro / triad** | The author's existing Claude Code helpers reused here (panel review / rate-limit throttle / convergence loop). *Internal helpers — not needed to understand the MVP.* |
| **Data-flow lock** | Synthesis may only use claims from `verified_claims.json`, and only `validate_ledger.py` produces it — so verification can't be skipped. |
| **High-risk claim** | A claim whose error is costly: numbers/%, currency, dates, legal/financial/causal assertions. **Classified by deterministic code** (§6.1). Compound claims are atomized (§6.1). |
| **conflict** | A computed condition: a claim with ≥1 `entails` AND ≥1 `contradicts` (§6.7). Recorded as a boolean; not a verdict label, not a final status. |
| **anchors_ok** | Derived: `span_matched AND numeric_ok`. |
| **effective_verdict** | The single per-`(claim,source)` verdict after producer-aware supersession (panel supersedes verifier, §6.8). All of §6.7 evaluates on effective_verdicts. |

---

## 1. Background & Motivation

**The pain:** AI research tools sound authoritative but routinely attach a *real* citation to a claim the source doesn't support. 받침 removes that — as far as is possible without a human in the loop.

**Starting point.** We fork `insane-research` and fix its two structural gaps:
- **Gap A — its "code gate" trusts LLM-set booleans** (never checks the source entails the claim).
- **Gap B — "2 independent sources" = distinct domain count** (syndicated content fakes independence).

### What we honestly claim (propagated to summary & §4)
The entailment *judgment* is made by LLMs (an isolated verifier + a panel). Code guarantees: (1) the quote verbatim-exists (anti-fabrication), (2) numbers/dates align (anti-number-swap), (3) ≥2 sources after near-dup collapse (closes Gap B), (4) fail-closed, signed, reproducible bookkeeping. **Quote-mining** — the dominant failure — is defended by the **M2 panel** (in the MVP) plus the **human-labeled precision gate** (G3), *not* by M1's anchors alone. We do not claim "truth proven in code"; we claim a panel-checked, auditable, fail-closed gate whose superiority is **measured** against insane-research on human labels (§9). Residual trust (verifiers are LLMs, panel lenses share a base model → R4) is tracked in §12.

---

## 2. Goals / Non-Goals

### Goals
- G1. Every high-risk claim is promoted only when, on `effective_verdicts`: ≥2 source-independent `entails` (incl. ≥1 A/B source within the entailing set), all proof spans verbatim-match the frozen snapshot, numeric/date anchors pass, **and the M2 panel reaches 2-of-3 consensus** (§6.7/§6.8).
- G2. Sign the full **input-closure** of `validate_ledger` so a pass is reproducible and **corruption-/skip-evident** (threat model §6.5; not author-tamper-proof, NG5).
- G3. Beat insane-research on a **pre-registered** benchmark on human-labeled entailment precision/recall, **stratified by failure-mode** (fabrication / quote-mining / number-swap) — §8/§9.
- G4. Low-friction Claude Code plugin (`/batchim "<topic>"`).

### Non-Goals (v1)
- NG1. No long-running self-hosted model servers (ephemeral local scripts / MCP allowed).
- NG2. No hosted SaaS / web product. NG3. Batch, single-session only. NG4. Not a web-search-stack replacement.
- NG5. **Not author-tamper-proof.** Signing detects accidental mutation / torn writes / pipeline-skip, not a motivated author holding the local key (§6.5). External anchor (git/timestamp) is an optional add.

---

## 3. Usage Example

```
> /batchim "Did the EU AI Act ban real-time biometric identification in public spaces?"
[batchim] scope → plan → retrieve(+snapshot) → dedup → verify → panel → synthesize
Report: RESEARCH/eu_ai_act_biometric_20260623/outputs/
  ✓ 14 high-risk claims verified (source-matched quote + panel-confirmed)
  ⚠ 3 quarantined → "Unresolved"   ⚠ coverage: full (no budget skips)
  ✗ 1 refuted → "Refuted"
```
> **Quarantine is a feature.** High quarantine on contested topics is expected and correct.

**The differentiator, concretely:** insane-research could mark *"the Act bans all real-time biometric ID"* verified because a blog asserts it. 받침's isolated verifier reads the cited text, sees *"…with law-enforcement exceptions,"* and the **panel's refute lens** confirms the quote doesn't entail the absolute claim → **quarantined**, not asserted. (M1 flags; **M2 panel closes the quote-mining case** — which is why the panel is in the MVP.)

---

## 4. Differentiation

| | Generic bot | insane-research | **받침** |
|---|---|---|---|
| Verification | "be accurate" prompt | Gate over **LLM-set** booleans | Gate over isolated-verifier verdicts **+ N=3 panel** *(verdict = LLMs; span/number = code)* |
| Claim↔evidence | Implicit | `src_id`, unchecked | Verdict **+ verbatim-span match in frozen snapshot** |
| Quote-mining | No defense | No defense | **Panel refute-lens (in MVP)** + human-precision metric |
| Independence | None | Distinct-domain (fakeable) | Canonical-URL + near-dup collapse (M1) → semantic (M3) |
| Auditability | None | Source list | **Auditable ledger** + signed input-closure manifest |

**Moat:** a public, adversarial, third-party-topic-selected benchmark where 받침 beats baselines on *human-judged* grounding **by failure-mode slice**, plus an inspectable ledger. We sell *"an auditable research ledger,"* not *"less hallucination."*

---

## 5. Architecture Overview

```
batchim/skills/batchim-main/scripts/
  classify_risk.py   # deterministic high-risk classifier + compound-claim atomization (regex/gazetteer/POS, NO LLM/network) → risk_classifications.jsonl
  snapshot.py        # freeze source text + content hash
  dedup.py           # M1: canonical-URL + simhash → independence_partition.json (frozen); M3: + semantic
  entail_gate.py     # isolated verifier per (high-risk claim × cited span) + anchors → entailment_verdicts.jsonl
  panel.py           # M2: N=3 prompt-diverse lenses, 2-of-3 consensus → panel verdicts (producer=panel)
  validate_ledger.py # SOLE joiner: join → decide(§6.7 on effective_verdict) → sign(§6.5); internal stages separated (D5)
  eval_report.py     # metrics (§9) incl. coverage invariant + degraded_verdict_rate
```

### Pipeline (one writer per artifact; finalize = single-rename commit, §6.5)
```
1 Scope → 2 Plan → 3 Retrieve(+snapshot) → 3.5 dedup(independence_partition, frozen, source set frozen here) → 4 Triangulate
        author writes claim_ledger.jsonl + claim_evidence_refs (author-owned, immutable; claimed_*)
                                  ▼
   4.5 entail_gate.py: classify_risk(code, atomize) → per high-risk claim × cited span:
        isolated verifier {entails|neutral|contradicts} + verbatim-span match(frozen snapshot) + numeric/date check
   4.6 panel.py (M2, in MVP): N=3 lenses on high-risk/contested claims → panel verdicts (supersede verifier)
        → entailment_verdicts.jsonl (gate-owned; each bound to claim_text_hash + snapshot_hash + verifier_prompt_hash + model_id)
                                  ▼
   validate_ledger.py (SOLE joiner): derive effective_verdict → §6.7 → verified|unresolved|refuted
        + signed manifest (input-closure) ; coverage invariant checked HERE
                                  ▼
5 Synthesis (verified-only) → 6 QA (+ body re-classification backstop, §6.1) → 7 Output ── eval_report.py HARD gate (§6.6)
```

---

## 6. Functional Requirements

### 6.1 Deterministic risk classification + atomization
- FR-R0. `classify_risk.py` computes `computed_risk` using **regex + fixed gazetteers + POS rules only — NO LLM, NO network** (preserves "not by the LLM" + NFR-3). It **over-classifies** (false-high cheap, false-low = leak); target **`risk_recall ≥ 0.98`** on a labeled fixture. **Compound high-risk claims are atomized** (or lint-rejected at ledger write) so the verifier judges a span against an **atomic** claim — a span must entail the *whole* atomic claim (closes the conjunctive partial-entailment leak). Output: gate-owned `risk_classifications.jsonl`. Gazetteer/rule **data files are hashed in the manifest** separately from `classifier_version`.
- FR-R1 (backstop). At Phase 6, re-run `classify_risk.py` over **rendered body sentences**; if any body sentence trips a high-risk rule but maps to no verified claim ⇒ **exit 2** (turns the static recall number into a runtime invariant).

### 6.2 Independence (closes Gap B in MVP)
- FR-I0. M1 independence = distinct `cluster_id` after `dedup.py` (canonical-URL + normalized-text simhash + pub-time clustering), emitted as frozen `independence_partition.json` (`source_id → cluster_id`), deterministic (stable tiebreak by `source_id`). **The source set is frozen at end of Phase 3.5; no new sources may be added afterward within a run** (a new source ⇒ new ledger version / new run). M3 = semantic upgrade (distinguish content near-dup from provenance dependence).

### 6.3 Entailment gate (M1)
- FR-E1. Per high-risk atomic claim, run the isolated verifier on each cited span (input = `(atomic_claim, span + fixed context window, source text)`). Persist span lifecycle `done|failed` and label `entails|neutral|contradicts`. Timeout ⇒ `failed`; one retry (separate retry budget, §7); then the claim's status falls to fail-closed handling. No span `pending` at finalize.
- FR-E2. Anchors (Appendix B): `span_matched` (verbatim, normalized) + `numeric_ok`; `anchors_ok := span_matched AND numeric_ok`. Anchors apply **symmetrically** to `entails` and `contradicts`. A label with `anchors_ok=false` cannot promote, refute, or trigger conflict (it cannot count).
- FR-E3. `validate_ledger.py` MUST assign each high-risk claim exactly one status via the §6.7 ordered algorithm on `effective_verdict`s, reading only `computed_*` (+ ids/text for joining).
- FR-E4. **Fail-closed:** a high-risk claim with no verdict tuple (`missing`), only `failed`/`malformed`/anchor-failed/budget-skipped verdicts, gets terminal **`unresolved`** with a recorded reason (`missing | failed | malformed | skipped_budget`). These are **not** structural errors (not exit 2).

### 6.4 Artifact ownership & schema
- FR-A1. `claim_ledger.jsonl` + `claim_evidence_refs` (`claim_id, source_id, cited_quote, context_window_id`) author-owned, immutable after write (append-only new records allowed pre-`validate_ledger`; corrections = new ledger version). `claimed_*` only.
- FR-A2. Gate-owned (`computed_*`): `risk_classifications.jsonl`, `independence_partition.json`, `entailment_verdicts.jsonl` (verifier + panel rows, append-only).
- FR-A3. `validate_ledger.py` sole joiner → `verified_claims.json`.
- FR-A4. Every artifact has `schema_version`. A *parseable record with an unknown enum* ⇒ claim `unresolved` + `validation_error`. A *structurally unparseable artifact / orphan id / hash-binding failure* ⇒ exit 2.
- FR-A5. Binding integrity (exit 2): every `source_id` resolves in `sources.jsonl`; every verdict's `claim_text_hash`/`snapshot_hash`/`cluster_id` matches current artifacts; grade is read **only** from `sources.jsonl.quality_rating` (verdict `source_grade` is a copy and must agree); stored `span_char_start/end` must re-extract to exactly `evidence_span` (duplicate spans ⇒ occurrence index).

### 6.5 Tamper-evidence, replay, commit
- FR-S1. The signed **manifest = the closure of every input to `validate_ledger`**: `input_hashes` = {claim_ledger, claim_evidence_refs, sources.jsonl, ordered `{source_id, snapshot_path, snapshot_hash}` (every source has exactly one frozen snapshot), independence_partition, risk_classifications + gazetteer-data hash, entailment_verdicts, resolved config (caps/thresholds/grade-map/**context-window config**), **verifier_prompt_hash + model_id + decoding params**, and **code/logic versions** (classify_risk, dedup, entail_gate, panel, validate_ledger, decision-table)}. `output_hashes` = {verified_claims}. `enabled_producers` recorded; **no consumed verdict may have a `producer` outside `enabled_producers`** (exit 2). For G3 reproducibility, the **benchmark topic-set hash, threshold vector, and human-label-set hash** are also signed (frozen at M0). sha in the committed run record.
- FR-S2. Determinism scoped to `validate_ledger` over the signed closure. On resume, replay frozen verdicts; re-query only spans with no frozen verdict. A frozen verdict whose hash-binding **mismatches** ⇒ if explained by an append-only new ledger version, **invalidate & re-query that verdict**; if unexplained (same ledger version, different hash) ⇒ **exit 2** (tamper). Cross-version: any signed `*_version` outside the running tool's supported set ⇒ **exit 2 + explicit migration command** (no silent upgrade).
- FR-S3. **Single-rename commit:** write all outputs to a `run_id` staging dir; the **`CURRENT`-pointer rename is the sole atomic commit point** and targets a per-run record containing the manifest sha. Lock/heartbeat live in a **separate** file (not the committed record). On startup, trust only `CURRENT → run_id` whose manifest verifies byte-for-byte; incomplete staging dirs are **discarded** (roll-forward only on full byte-verify).
- FR-S4. **Threat model:** signing/commit detect accidental mutation, torn writes, and pipeline-skip — **not** a motivated author (NG5). Docs separate `audit_integrity` (signing) from `entailment_correctness` (human-precision metric). A report file carries the `run_id`+sha it was synthesized from; Phase-7 refuses to publish a report whose manifest is `superseded_by != null`.

### 6.6 Exit-code & error taxonomy
- FR-X1. exit **0** = ran, allowlist written; **1** = ran, 0 verified (legitimate abstention; report contains no high-risk body claims) **or completed-degraded** (cap-exhausted, see NFR-1); **2** = structural error only (unparseable artifact, orphan id, hash-binding mismatch, incomplete commit, `enabled_producers` violation, body-backstop FR-R1 hit). Synthesis requires a **positive** check: valid signed manifest present, coverage status acceptable, lock released — not merely "no exit 2."
- FR-X2. `eval_report.py` Phase-7 hard gate: FAIL (exit 2) if `missing_entailment_proof_rate>0` OR `citation_resolution_rate<100%` OR coverage invariant (FR-X3) fails. The coverage invariant is **also** enforced inside `validate_ledger` (so a signed manifest can't exist for a coverage-incomplete run); eval is the redundant backstop.
- FR-X3. **Coverage invariant — terminal *claim-status* coverage:** every high-risk claim has either a frozen verdict-derived status or an explicit `not_run_reason`. A `skipped_budget` claim satisfies coverage **only** if flagged `coverage_degraded=true`, and the run is reported as outcome class **completed-degraded** (≠ completed-full) — a silent skip (no reason) FAILS.

### 6.7 Decision algorithm (single source of truth; evaluates on `effective_verdict`)
Per high-risk atomic claim, build tuples `(normalized_verdict ∈ {entails,neutral,contradicts,failed,malformed,missing}, anchors_ok, cluster_id [via independence_partition[source_id]], quality_rating [via sources.jsonl], producer, cited)`.
**Derivations:** `anchors_ok := span_matched AND numeric_ok`; `failed|malformed|missing` and `anchors_ok=false` ⇒ count as **neutral** (cannot promote/refute/conflict), but are **recorded**. If a claim has **zero** tuples ⇒ status `unresolved` (reason `missing`) — a terminal claim status for FR-X3.
Apply **in order** (on effective_verdicts):
0. **missing** — no tuples ⇒ `unresolved` (missing).
1. **structural** — orphan id / schema break / binding failure ⇒ **exit 2**.
2. **refuted** — ≥1 anchored `contradicts` from an **A/B** source. *(Intentional: an A/B contradiction dominates coexisting A/B entails. M2: a refutation is overturned only by a **claim-level panel re-vote**, not by a panel verdict on a different source — FR-P3.)*
3. **conflict ⇒ unresolved** — ≥1 anchored `entails` AND ≥1 anchored `contradicts` (any grade) ⇒ `unresolved`, `conflict=true`.
4. **verified** — iff all: (a) ≥2 anchored `entails` from **distinct `cluster_id`s including ≥1 A/B within that entailing set**; (b) **(M2) the panel reached 2-of-3 consensus `entails`** for the claim; (c) no blocking condition above.
5. **unresolved** — otherwise.
**Cited-but-unused:** only `proof_source_ids` must pass anchors; non-proof citations that are `neutral`/unmatched are dropped from the body, not penalized.
Non-high-risk claims follow inherited cite-and-write **after** `classify_risk` confirms not-high-risk; **all** claims (any risk) still get citation-resolution + source-existence checks (§9).

### 6.8 prism panel (M2 — in MVP) & RAG (M3 — post-MVP)
- FR-P1. Per high-risk/contested claim, **N=3** prompt-diverse lenses (refute / source-quality / numeric-consistency), **model/config-diverse where available**. **Consensus = 2-of-3**; a 1-1-1 split or any missing/failed vote ⇒ **quarantine (`unresolved`)**. Disagreement ⇒ triad convergence, **hard cap 3 rounds**.
- FR-P2. Throttle all verifier/panel fan-out to 2–3 concurrent (single OS process, async workers) with **reserve-before-dispatch** atomic budget counter (3 workers can't each see budget=1 and all fire); liveness + sequential fallback (ddaro guard).
- FR-P3. Producer-aware: raw verdicts append-only with `producer`; `validate_ledger` derives one `effective_verdict` per `(claim,source)` — **panel supersedes verifier when present** (`supersedes_verdict_id`). A refutation override is a **claim-level** panel re-vote (not cross-source). The MVP runs with `enabled_producers=["verifier","panel"]`; an M1-only run is a degraded mode whose manifest is a distinct producer-set and is **never** mutated into an M2 manifest (M2 produces a new `run_id`, additive — never destroys a signed historical verdict).
- FR-R3. M3: embeddings + cross-encoder rerank + hybrid retrieval + query expansion; committed local-script default, MCP if present, lexical fallback (NFR-5).

### 6.9 Inherited
Data-flow lock; abstention; resumable `state.json`; A–E grading; templates; `/batchim`, `resume`, `status`, structured-JSON query.

---

## 7. Non-Functional Requirements
- **NFR-1 Cost.** Caps: `max_verifier_calls` (120), `max_panel_calls`, `max_spans_per_claim` (3); separate retry budget. `/batchim status` shows a **coarse upper-bound** estimate pre-launch. **Cap-exhaustion:** finalize a claim `verified` only if **all its cited spans** have terminal verdicts (so an unqueried `contradicts` can't be skipped into a false verified); otherwise force `unresolved (skipped_budget)`; run completes as **completed-degraded** (FR-X3), resumable via frozen verdicts. Cost cap > abstention cap in precedence (a run is never structurally impossible; it reports degraded coverage).
- **NFR-2 Reliability.** Per-call timeout → `failed` → one foreground retry → quarantine. Liveness checks; no silent background death.
- **NFR-3 Determinism (scoped).** `validate_ledger` output + signature reproducible given the signed closure. Verifier/panel generation not claimed deterministic.
- **NFR-4 Concurrency.** Single session (NG3); lock acquired before Phase 1. Lock record = `{pid, pid_start_time|boot_id|nonce, heartbeat_ts}`; "PID alive" = same pid **and** start-time/nonce (defends PID reuse). Reclaim only if `heartbeat stale AND PID dead`; `stale AND alive` ⇒ refuse + `--force`. Per-file atomic temp-then-rename; cross-file consistency via FR-S3.
- **NFR-5 Degradation.** Missing MCP ⇒ WebSearch/WebFetch; missing embedding backend ⇒ lexical dedup; recorded in `state.json`.
- **NFR-6 Privacy.** Artifacts local. Egress: search queries + `(claim, span)` pairs to configured providers; no telemetry.

---

## 8. MVP Scope & Phasing  (MVP = M0 + M1 + M2)

| Milestone | Scope | Done when |
|---|---|---|
| **M0** Fork & baseline | Fork → rebrand 받침; run end-to-end; **freeze benchmark (third-party-selectable topics) + insane-research baseline + human-label protocol + signed thresholds** | report produced; **topic-set + label-set + threshold vector frozen & signed**; baseline metrics recorded |
| **M1a** Vertical slice ★first | risk classify+atomize + isolated verifier + span/number anchors + `verified_claims.json` (NO signing/commit/replay yet) | **false-entail rate measurable** vs human labels on the fixtures — the core experiment, before durability machinery |
| **M1b** Durability | FR-A1–A5, FR-S1–S4, FR-X1–X3, §6.7, FR-P2 throttle, Appendix A/B | `missing_entailment_proof_rate=0`; coverage invariant holds; reproducible signed manifest |
| **M2** Panel (in MVP) | FR-P1, FR-P3, §6.7(4b) | quote-mining defended: panel 2-of-3 consensus gates verified; **received human-precision stratified by failure-mode**; beats insane-research on `false-entail` by the pre-registered margin |
| **M3** RAG (post-MVP) | FR-I1, FR-R3 | semantic dedup changes independence; rerank raises `verified_recall` without raising `leak_rate` |

**Human-label protocol (M0):** ≥2 independent labelers blind to the system's verdict; written rubric; label unit = `(atomic_claim, span)`; **Cohen's κ ≥ 0.7** (raised from 0.6); `n` sized to bound false-entail rate with a stated CI; **pre-registered topic-selection + claim-sampling + exclusion rules** (third-party or criteria-based, not author cherry-pick); an **adversarial slice** (contested/legal/causal/numeric, and a held-out subset where labelers see the *full source*, not just the cited span, to measure span-selection bias). Report metrics **by failure-mode slice**.

---

## 9. Success Metrics (thresholds pre-registered & signed before tuning)
**Structural (gate-enforced):** `missing_entailment_proof_rate=0`; `citation_resolution_rate=100%` (all claims, any risk); `span_match_rate=100%` (verified); coverage invariant (FR-X3).
**Correctness (external — the bar):** `entailment_precision`/`recall` vs human labels; **false-entail rate is the headline, with CI, stratified by failure-mode (fabrication/quote-mining/number-swap).**
**Health (anti-gaming, gated):**
- `abstention_rate`/`quarantine_rate` — capped.
- `degraded_verdict_rate` (fraction of spans finalized via failed/malformed) — surfaced + capped (distinguishes "abstained cleanly" from "half-died and shipped").
- `leak_rate` *(= fraction of unresolved+refuted claims appearing assertively in the body; inherited eval)* — below baseline by pre-registered margin.
- **`verified_recall` *(= verified high-risk ÷ total high-risk)* — GATED**: 받침 must verify ≥ Y% of the claims insane-research correctly verified per human labels (so abstention can't be a free win on `leak_rate`).

A/B: gate-on vs off, and 받침 vs insane-research, on the frozen topics; all thresholds pre-registered & signed.

---

## 10. Key Tech Decisions
- D1. Engine = isolated verifier subagents + N=3 panel + mechanical anchors (not hosted NLI). Local NLI/cross-encoder = M3 option.
- D2. Embeddings (M3): committed local script / MCP / lexical fallback.
- D3. Reuse prism/ddaro/triad. D4. Versioned superset schemas, `claimed_*`/`computed_*`.
- D5. `validate_ledger.py` internally = **join → decide(§6.7) → sign** as pure stages (decision logic golden-tested against frozen fixtures for **every** §6.7 branch, independent of crypto).

---

## 11. Open Questions
- ~~Q1 Name~~ → 받침. ~~Q5 Benchmark~~, ~~Q-scope (M2-in-MVP)~~ → resolved.
- Q2. Distribution: standalone repo + list in `haroom_plugins` (recommended).
- Q3. ~~Granularity~~ → claim-vs-span **with fixed context window** (decided); full-chunk retrieval = M3.
- Q4. Inherited reference docs to keep verbatim vs rewrite (M0).
- Q6. ~~Panel necessity~~ → **resolved: panel is in the MVP.** Verifier *independent contrary-retrieval* (beyond author's span) still optional → evaluate as an M2 lens enhancement.

---

## 12. Risks
- R1. Residual verifier/panel trust (LLMs). Mitigation: anchors + panel + human-precision launch gate; honest framing (§1).
- R2. Quote-mining via author-picked span. Mitigation: fixed context window; panel refute-lens (MVP); held-out full-source labeling slice (§8).
- R3. **Correlated model error in the panel** (lenses share a base model). Mitigation: model/config diversity where available; treat panel as *prompt-diverse* not independent; ship panel only if it beats single-verifier on human labels (M2 done-when).
- R4. Cost/complexity. Mitigation: M1a vertical slice first (measure before durability); high-risk-only; caps + cap-exhaustion (NFR-1); make `validate_ledger` "aggressively boring" with golden fixtures (D5).
- R5. Rate limits → throttle from M1 (FR-P2). R6. Stale web content → snapshots+hashes (FR-S1).
- R7. Benchmark gaming → third-party/criteria topic selection, κ≥0.7, failure-mode stratification, full-source adversarial slice (§8).
- R8. Scope creep → strict phasing. R9. License → NOTICE + correct upstream link (§13).

---

## 13. Attribution
Derivative of **`fivetaku/insane-research`** (via the `fivetaku/gptaku_plugins` marketplace; MIT). Retains data-flow-lock + eval methodology; adds deterministic risk classification + atomization, source snapshotting, the entailment gate with mechanical anchors, the N=3 panel, explicit artifact-ownership & input-closure signing, lexical/semantic dedup. License: MIT + NOTICE crediting upstream.

---

## Appendix A — Artifact Schemas (finalize in M0)
```jsonc
// sources.jsonl
{ "id":"src_001","url":"…","canonical_url":"…","domain":"…","quality_rating":"A|B|C|D|E",
  "fetched_at":"…","content_hash":"sha256:…","snapshot_path":"…","byline":null,"wire":null,"schema_version":1 }
// claim_ledger.jsonl (AUTHOR-OWNED, immutable; claimed_*)  — claims are ATOMIC after classify_risk atomization
{ "claim_id":"clm_001","text":"…","claim_text_hash":"sha256:…","claimed_risk":"high|normal",
  "atomic":true,"claimed_source_ids":["src_001","src_003"],"schema_version":1 }
// claim_evidence_refs.jsonl (AUTHOR-OWNED) — defines verifier input, closed & replayable
{ "claim_id":"clm_001","source_id":"src_003","cited_quote":"…","context_window_id":"cw_007","schema_version":1 }
// risk_classifications.jsonl (GATE-OWNED)
{ "claim_id":"clm_001","computed_risk":"high|normal","atomized_from":null,"matched_rule_ids":["num"],
  "classifier_version":"…","gazetteer_hash":"sha256:…","schema_version":1 }
// independence_partition.json (GATE-OWNED, frozen)
{ "source_set_id":"…","dedup_version":"…","clusters":{"src_001":"cl_A","src_003":"cl_B"},"schema_version":1 }
// entailment_verdicts.jsonl (GATE-OWNED; computed_*; append-only; verifier + panel rows)
{ "verdict_id":"v_001","claim_id":"clm_001","source_id":"src_003","producer":"verifier|panel",
  "panel_round":null,"lens":null,"vote":null,"supersedes_verdict_id":null,
  "label":"entails|neutral|contradicts","span_state":"pending|done|failed","fail_reason":null,
  "evidence_span":"…","span_char_start":1234,"span_char_end":1310,"occurrence_index":0,
  "span_matched":true,"numeric_ok":true,"source_grade":"A",
  "claim_text_hash":"sha256:…","snapshot_hash":"sha256:…","verifier_prompt_hash":"sha256:…",
  "model_id":"…","schema_version":1 }
// verified_claims.json (validate_ledger output; computed status only)
{ "claim_id":"clm_001","status":"verified|unresolved|refuted","status_reason":"…|missing|failed|malformed|skipped_budget",
  "conflict":false,"coverage_degraded":false,"independent_entails":2,"panel_consensus":"entails|null",
  "proof_source_ids":["src_001","src_003"],"proof_grades":["A","B"],"refuted_by":null }
// manifest (signed; sha in committed run record)
{ "manifest_version":1,"run_id":"…","enabled_producers":["verifier","panel"],"superseded_by":null,
  "input_hashes":{"claim_ledger":"…","claim_evidence_refs":"…","sources":"…",
     "snapshots":[{"source_id":"src_001","snapshot_path":"…","snapshot_hash":"…"}],
     "independence_partition":"…","risk_classifications":"…","gazetteer":"…","entailment_verdicts":"…",
     "resolved_config":"…","context_window_config":"…","verifier_prompt":"…","model_id":"…",
     "benchmark_topics":"…","thresholds":"…","human_labels":"…"},
  "output_hashes":{"verified_claims":"…"},
  "code_versions":{"classify_risk":"…","dedup":"…","entail_gate":"…","panel":"…","validate_ledger":"…","decision_table":"…"} }
```

## Appendix B — Span-match normalization (normative)
`span_match(span, snapshot)`: apply identically to both, then test contiguous substring:
1. Unicode **NFKC**. 2. Decode HTML entities. 3. Fold smart quotes/dashes/ellipses to ASCII. 4. Collapse Unicode whitespace (incl. NBSP) → single space; strip ends. 5. **Case-sensitive.** Match = contiguous; paraphrase/non-contiguous ⇒ fail. Store `span_char_start/end` + `occurrence_index`; **re-extraction at those coordinates must equal the normalized `evidence_span`**. **An M1 fixture corpus of `(snapshot, span, expected)` cases is the acceptance test** (distinguishes a normalization bug from genuine fabrication).
