# 받침 (Batchim)

> **받침** — the final consonant that *supports* a Korean syllable. Here: the evidence that must support every claim.

A Claude Code plugin for **deep research that verifies its claims against evidence** — an isolated model judges whether each citation supports its claim, a panel of independent lenses cross-checks the risky ones, and **code mechanically enforces** that the quoted text really exists and the numbers/dates line up. Anything it can't confirm is quarantined.

```
/batchim "Did the EU AI Act ban real-time biometric identification in public spaces?"
→ a cited report where every high-risk claim is panel-confirmed + source-matched,
  plus an auditable, signed ledger.
```

## Status

**MVP gate built (M0–M3 code complete; formal human labeling pending).** Forked
from [`fivetaku/insane-research`](https://github.com/fivetaku/gptaku_plugins) (MIT,
see [`NOTICE`](NOTICE)); the verification core is essentially all new. Design:
[`docs/PRD.md`](docs/PRD.md) (v0.4) + [`docs/M0-PLAN.md`](docs/M0-PLAN.md). **228
tests** green across 16 files.

### What's built (`skills/batchim-main/scripts/`, `bench/`)

| Milestone | Built | Modules |
|---|---|---|
| **M1** entailment gate | risk classify + atomization, source snapshot+hash, isolated-verifier anchors, §6.7 decision, single joiner | `classify_risk` · `snapshot` · `anchors` · `entail_gate` · `decide` · `validate_ledger` |
| **M1** independence | canonical-URL + simhash clusters | `dedup` |
| **M2** panel (MVP) | N=3 prompt-diverse lenses, 2-of-3 consensus → quote-mining defense | `panel` |
| **M1b** durability | signed input-closure manifest, single-rename `CURRENT` commit, replay + cross-version guard, publish gate, body backstop, budget throttle | `manifest` · `commit` · `replay` · `backstop` · `budget` |
| **Phase-7** §9 gate | leak / missing-proof / span-match / coverage / manifest hard gate | `eval_report` |
| **M0** measurement | Cohen's κ gate, human-gold scorer, benchmark freeze/sign | `bench/kappa` · `bench/score_benchmark` · `bench/freeze` |
| **M3** (post-MVP) | semantic independence (paraphrase syndication), hybrid RAG retrieval | `semantic` · `retrieval` |

Orchestration is wired in [`SKILL.md`](skills/batchim-main/SKILL.md) (Phase 3.5/4.5/4.6).
**Remaining:** real human labelers (≥2, κ≥0.7) + third-party topic lock for the
signed launch-gate number — tooling is ready (`bench/`, [`RUBRIC.md`](bench/labels/RUBRIC.md)).

### Measured (informal e2e — `bench/baseline/m1a_informal_smoke.md`)

End-to-end over 3 topics (fabrication / number-swap / quote-mining), false-entail rate:

| | M1 anchors only | + M2 panel |
|---|---|---|
| false-entail | 1/6 | **0/6** |
| false-negative | 0/6 | **0/6** |

Code anchors block fabrication + number-swap deterministically; the panel closes
the hard quote-mine (its refute lens cited EU AI Act Art 5(1)(h) exceptions).
*Informal — draft topics, no human labels, not the signed benchmark.*

## Why it's different

| | insane-research (upstream) | 받침 |
|---|---|---|
| Verification | deterministic gate over **LLM-set** booleans | gate over isolated-verifier verdicts **+ N=3 panel** *(verdict = LLMs; span/number checks = code)* |
| Claim↔evidence | `src_id`, unchecked | verdict **+ verbatim-span match in a frozen source snapshot** |
| Quote-mining | no defense | **panel refute-lens** (in the MVP) + a human-labeled precision metric |
| Independence | distinct-domain count (fakeable) | canonical-URL + simhash → **semantic (M3)** near-duplicate collapse |
| Auditability | source list | **signed input-closure manifest + content-addressed run, atomic commit, byte-verified replay** |
| Measurement | none | **pre-registered benchmark, κ-gated human labels, false-entail by failure-mode** |

We claim *"an auditable, fail-closed, panel-checked entailment gate,"* not *"truth proven in code"* — and we **measure** the difference against the baseline on human labels.

## License

MIT (see [`LICENSE`](LICENSE)). Derivative work — attribution in [`NOTICE`](NOTICE).
