# 받침 (Batchim)

> **받침** — the final consonant that *supports* a Korean syllable. Here: the evidence that must support every claim.

A Claude Code plugin for **deep research that verifies its claims against evidence** — an isolated model judges whether each citation supports its claim, a panel of independent lenses cross-checks the risky ones, and **code mechanically enforces** that the quoted text really exists and the numbers/dates line up. Anything it can't confirm is quarantined.

```
/batchim "Did the EU AI Act ban real-time biometric identification in public spaces?"
→ a cited report where every high-risk claim is panel-confirmed + source-matched,
  plus an auditable, signed ledger.
```

## Status

**Pre-build (M0).** This repo currently holds the design: see [`docs/PRD.md`](docs/PRD.md) (v0.4, build-ready) and the M0 plan in [`docs/M0-PLAN.md`](docs/M0-PLAN.md). The plugin is a fork-and-extension of [`fivetaku/insane-research`](https://github.com/fivetaku/gptaku_plugins) (MIT) — see [`NOTICE`](NOTICE).

The PRD was hardened across three dual-engine (Claude + Codex) review rounds; the round artifacts are preserved under `docs/prism-all/` and `docs/discussion/` as design provenance.

## Why it's different

| | insane-research (upstream) | 받침 |
|---|---|---|
| Verification | deterministic gate over **LLM-set** booleans | gate over isolated-verifier verdicts **+ N=3 panel** *(verdict = LLMs; span/number checks = code)* |
| Claim↔evidence | `src_id`, unchecked | verdict **+ verbatim-span match in a frozen source snapshot** |
| Quote-mining | no defense | **panel refute-lens** (in the MVP) + a human-labeled precision metric |
| Independence | distinct-domain count (fakeable) | canonical-URL + near-duplicate collapse |
| Auditability | source list | **auditable ledger + signed input-closure manifest** |

We claim *"an auditable, fail-closed, panel-checked entailment gate,"* not *"truth proven in code"* — and we **measure** the difference against the baseline on human labels.

## License

MIT (see [`LICENSE`](LICENSE)). Derivative work — attribution in [`NOTICE`](NOTICE).
