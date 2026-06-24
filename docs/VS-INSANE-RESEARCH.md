# 받침 vs insane-research — what advanced, and what's next

받침 is a fork-and-extension of `fivetaku/insane-research` (MIT). This doc states,
honestly, what changed and what could still improve. It is opinion + roadmap, not
a marketing sheet.

## What 받침 KEPT from insane-research (the good bones)
- **The data-flow lock** — synthesis may only consume `verified_claims.json`, and
  only one checker produces it, so verification can't be skipped (skipping leaves
  synthesis with no input). This is insane-research's best idea; 받침 strengthened
  it but did not invent it.
- 7-phase research flow, scoping/question UX, A–E source grading, abstention
  philosophy, multi-agent retrieval, output templates, the *idea* of a code eval.

## What advanced (with evidence)

| axis | insane-research | 받침 | why it matters |
|---|---|---|---|
| **Who decides "verified"** | deterministic gate over **LLM-set booleans** (LLM writes `verified`/`counter_refuted`; gate checks *process*: counter-search done? ≥2 domains?) | gate **computes** status from isolated-verifier *labels* + code anchors + §6.7 (`decide.py`) | the model can't write "verified" — it can only propose a label |
| **Claim↔evidence** | `src_id` attached, **unchecked** | **verbatim span-match in a frozen snapshot** + numeric/date anchors (`anchors.py`, `snapshot.py`) | a fabricated or number-swapped quote is blocked **in code**, not on trust |
| **Quote-mining** | **no defense** | **N=3 panel** refute/source-quality/numeric lenses, 2-of-3 (`panel.py`) | measured: false-entail **1/6 → 0/6** (refute lens cited EU AI Act Art 5(1)(h) exceptions) |
| **Risk classification** | LLM/implicit | **deterministic code**, over-classify, + **atomization** (`classify_risk.py`) | "not by the LLM" guarantee; closes the conjunctive ("X and Y") leak |
| **Independence** | distinct-domain **count** (fakeable) | canonical-URL + simhash → **semantic** near-dup (`dedup.py`, `semantic.py`) | "≥2 independent" can't be faked by syndication / paraphrase |
| **Reproducibility & audit** | a basic signature in state.json | **signed input-closure manifest, content-addressed run, atomic single-rename commit, byte-verified replay, supersede gate** (`manifest/commit/replay`) | a pass is reproducible and corruption-/skip-evident |
| **Measurement** | leak / citation eval | adds the **correctness** axis: false-entail vs **human labels**, **stratified by failure-mode**, **pre-registered + κ-gated** (`bench/`) | the honest claim "beats baseline on human-judged grounding," not "less hallucination" |
| **Fail-closed coverage** | abstention rules | **coverage invariant** (every high-risk claim terminal) + cap-exhaustion → completed-degraded; body backstop (FR-X3/R1) | an unqueried contradicting source can't be silently skipped into a `verified` |

One-line: insane-research **asks the model to be accurate and reads its booleans**;
받침 lets the model **only propose a label** while **code enforces the evidence
exists and computes the verdict**, the **panel** catches what code can't
(quote-mining), and the result is an **audited, reproducible ledger**.

## What we must NOT overstate (honesty ledger)
- The verifier and panel are **still LLMs** — not proven correct. 받침's claim is
  *"auditable, fail-closed, panel-checked entailment,"* not *"truth in code."*
- The headline **0/6 is INFORMAL** — draft topics, author-known answers, no κ≥0.7
  human labels. The real launch-gate number needs human labelers + third-party topics.
- The panel is **prompt-diverse, not model-independent** (correlated-error risk, R3).
- Signing detects **accident / torn write / skip — not a motivated author** (NG5).

## Where it can still advance (prioritized)

### Tier 1 — substantiate the core claim
1. **Real human labeling** (M0 0.4/0.5). The only thing that turns "0/6 informal"
   into a defensible "beats baseline." Tooling is ready (`bench/kappa`, `score_benchmark`,
   `freeze`, `RUBRIC.md`); needs ≥2 blind labelers + non-author topic lock.
2. **Model-diverse panel.** Run the 3 lenses on *different models* (Claude + Codex/GPT),
   not just different prompts — directly attacks the correlated-error caveat (R3) that
   currently weakens the quote-mining defense's credibility.
3. **Verifier-reliability harness.** Measure the isolated verifier's *own* false-entail
   rate vs human labels, so you know how much the anchors + panel are compensating for.

### Tier 2 — strengthen the code half (the real differentiator)
4. **Semantic numeric anchor.** Today it's literal co-occurrence. Add a *referent*
   check for the segment-vs-total / fiscal-vs-calendar / RRR-vs-ARR family (the NVIDIA
   "$130.5B total cited as Data Center" case is a real quote-mine the literal anchor
   misses) — still code, with explicit unit/scale rules, ambiguity routed to the panel.
5. **Negation / scope anchor.** A code check for polarity mismatch ("X is NOT prohibited"
   vs claim "X is prohibited") instead of trusting the verifier label alone.
6. **Contrary-retrieval lens** (PRD Q6). A panel lens that *independently searches* for
   refuting evidence rather than only reasoning over the cited sources — the strongest
   defense against omission/quote-mining (actively go find the exception).

### Tier 3 — provenance, ops, product
7. **Real provenance independence** — wire/byline/syndication + first-published-vs-reprint
   timestamp clustering, even a source-funding graph: distinguish *independent confirmation*
   from *echo*. This is the credibility of "≥2 independent sources."
8. **External anchor for signing** (NG5 mitigation) — optional git-commit / RFC-3161
   timestamp / transparency-log of the manifest sha, so audit resists a motivated author.
9. **Lock/heartbeat** (NFR-4, specced, unbuilt) — PID+start-time single-session lock with
   stale reclaim, for real concurrency safety.
10. **Inspectable ledger UI** — render each verified claim with its proof spans + panel
    votes in the report, so a human can audit *why* it passed, not just *that* it passed.
11. **Benchmark in CI** — run the (signed) benchmark on every change; track false-entail
    by failure-mode as a regression metric. Plus **ablations** (anchors-only vs +panel vs
    +semantic-dedup) to justify each component's token cost on the human-labeled set.

### Tier 4 — scope
12. Incremental/streaming research (append-only ledger versioning is specced),
    cross-report verified-claim memory (re-validate snapshots, don't re-verify facts).
