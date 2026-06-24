# 받침 — adoption plan, how to ask, and why it beats vanilla web research

From "working engine + informal demo" to "a tool people use and trust."

## Part A — the plan (demo → proven tool → product)

### Phase 0 — install & first real run (1 session)
Goal: prove the one-click UX, not just the scripts.
- [ ] Publish/point the plugin in `minwoo-data/haroom_plugins`; `/plugin install batchim`; restart.
- [ ] Run `/batchim` on **one real high-risk question** end-to-end (a legal/finance/medical one).
- [ ] Capture the session folder + `eval_report.json`; fix whatever breaks in the live flow.
- Exit: a real report exists in `RESEARCH/…/outputs/` with a signed manifest and a green Phase-7 gate.

### Phase 1 — pilot (1–2 sessions)
- [ ] Run 3–5 real questions across domains (law / finance / medical / tech-spec).
- [ ] For each, eyeball the Verified/Unresolved/Refuted split against known truth.
- [ ] Log: where the gate helped (blocked a wrong number / quote-mine), where it over-abstained, cost per run.
- Exit: a short "pilot findings" note — concrete wins + rough cost.

### Phase 2 — the proven number (needs people)
The one thing that turns "informal 0/6" into a defensible claim.
- [ ] Lock the benchmark: ≥5 topics chosen by a **non-author** (anti-gaming); `bench/freeze.py`.
- [ ] **≥2 blind human labelers** label `(claim, span)` per `RUBRIC.md`; `bench/kappa.py` until κ≥0.7; adjudicate → `gold.jsonl`.
- [ ] `bench/score_benchmark.py`: report false-entail by failure-mode vs the insane-research baseline.
- Exit: one signed table — "받침 beats baseline on quote-mining/number-swap false-entail by X."

### Phase 3 — package & ship
- [ ] Model-diverse panel live on Codex CLI (wire `assign_lenses`); CI runs the benchmark on every change.
- [ ] An inspectable report view (each verified claim → its proof span + panel votes).
- [ ] Tighten cost: cap high-risk claims per run; surface the pre-launch cost estimate.
- Exit: a README quickstart + the proven number + a sample report → shareable.

## Part B — how to ask /batchim (it rewards high-risk, checkable questions)

받침 only adds value where claims are **checkable** (numbers, dates, legal/causal). Phrase
questions so the answer hinges on facts a source can confirm or refute.

| weak prompt | strong prompt (high-risk, checkable) |
|---|---|
| "Tell me about the EU AI Act." | "Does the EU AI Act **ban** real-time remote biometric ID in public spaces, or allow exceptions?" |
| "How is NVIDIA doing?" | "What was NVIDIA's **Data Center segment revenue in FY2025** per its 10-K, and the YoY %?" |
| "Is statin X effective?" | "What **absolute risk reduction** did trial Y report for statin X in primary prevention?" |
| "React vs Vue?" | "Does **HTTP/3 (RFC 9114) mandate TLS 1.3** for all connections?" |

Rules of thumb:
1. **Make it answerable by a primary source** (law text, filing, RFC, peer-reviewed trial).
2. **Name the exact quantity / scope** (segment not company, fiscal not calendar, absolute not relative) — the anchors check exactly that.
3. **Time-bound it** ("FY2025", "as of 2026") so sources are snapshot-stable.
4. **Invite the exception** ("…or are there carve-outs?") — that's where the panel earns its keep.
5. Use **strict mode** for law/medical/finance; default mode for broad exploration.

## Part C — why this beats vanilla Claude Code web research (and by how much)

Vanilla `WebSearch`/`WebFetch` research: the model searches, reads, summarizes, and cites
URLs. It is fast and great for **exploration**. But it **trusts the model**: nothing checks
that a quoted sentence actually exists in the source, that a number's scale is right, that a
cited quote actually *entails* the claim, or that an unverified claim didn't slip into the body
as fact. There is no audit trail and no enforced abstention.

| dimension | vanilla web research | 받침 | how much it matters |
|---|---|---|---|
| Quote really exists in the source | not checked | **verbatim span-match in a frozen snapshot** | kills fabricated/paraphrased quotes outright |
| Number is right (scale/unit) | model's word | **code: $4.2bn ≠ $4.2m, 8% ≠ 8** | the #1 silent error in finance/medical answers |
| Polarity ("not prohibited") | model's word | **code: negation-inversion rejected** | flips a conclusion 180° if missed |
| Quote-mining (true quote, wrong claim) | **no defense** | **N=3 panel + active contrary-search** | the dominant "confident-but-wrong" mode |
| Independent corroboration | "two links" | **canonical-URL → semantic → wire/byline** dedup | stops echo-chamber faking "2 sources" |
| Unverified claim leaking into the body | happens freely | **data-flow lock: body uses verified-only** | the difference between a draft and a record |
| Reproducible / auditable | no | **signed manifest, atomic commit, replay** | "where did this come from?" has an answer |

**How much better — honestly:**
- For **casual / exploratory** questions ("what's new in X"): vanilla is *fine and cheaper*.
  받침's machinery is wasted there.
- For **high-risk, checkable** claims (a number, a legal scope, a causal/medical effect):
  vanilla's failure modes (fabricated quote, scale slip, dropped exception, quote-mine) are
  exactly the ones 받침 is built to catch — and on the informal e2e it caught **3/3** of those
  classes (fabrication + number-swap by code, quote-mining by the panel), driving false-entail
  to **0** where the verifier-only path leaked 1.
- The honest headline isn't "fewer hallucinations" — it's: **vanilla gives you an answer;
  받침 gives you an answer plus a code-checked, panel-confirmed, signed reason to believe each
  high-risk claim — and an explicit list of what it could *not* confirm.**

That last part (the *Unresolved/Refuted* list) is the real product: vanilla never tells you
what it failed to verify. 받침 does, by construction.
