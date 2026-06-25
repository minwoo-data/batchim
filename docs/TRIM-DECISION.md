# Trim decision — dead fork-inherited code + doc sprawl

Decision record for the session that measured `verified_recall` and run cost. The
governing rule was "prove the number before more engineering"; the trims below are
justified by a **correctness finding**, not LOC vanity.

## What was removed

| Path | LOC | Why |
|---|---|---|
| `skills/batchim-main/scripts/orchestrator.py` | 397 | Unused fork-inherited session state-machine (`ResearchPhase`/`ResearchOrchestrator`/`init_research`/…). Not imported by any live script, not covered by any test. SKILL.md does all orchestration via prompt; these stubs have "no execution authority" (SKILL.md's own words). |
| `skills/batchim-main/scripts/pipelines.py` | 433 | Same: unused, untested. **Plus a correctness liability** — it carried `classify_claim_status()` and `strict_verification_handoff()`, a SECOND implementation of §6.7 claim-status logic that diverges from the authoritative `decide.py` / `validate_ledger.py`. The batchim thesis is "**one** sole joiner computes status"; a shadow classifier in untested code undermines that invariant the moment anyone imports it. |
| `docs/PRD-v0.1.md`, `docs/PRD-v0.2.md`, `docs/PRD-v0.3.md` | — | Superseded by `docs/PRD.md` (v0.4). Pure version history; git preserves it. Doc sprawl. |

Total: **830 LOC of untested, unimported code** + 3 stale PRD snapshots.

## Why this is safe
- `grep` repo-wide: neither file is `import`ed anywhere; no `tests/` reference them.
- The only live pointers were three SKILL.md prose mentions (handoff §, script
  table, orchestration note). All three were rewritten in-place:
  - the handoff-selection rule (`strict_verification_handoff`) was inlined as prose
    (unresolved + high-risk only; status authority stays with the sole joiner);
  - the script table now lists `budget.py` instead, and the orchestration note
    states explicitly that no state-machine script exists by design.
- `contrary.py` / `replay.py` use the *word* "orchestrator" to mean **SKILL.md**,
  not the deleted file — left untouched.
- Full suite re-run after deletion: **21 files / 377 assertions green**, unchanged.

## What was NOT trimmed (and why)
- The 12 authoritative gate scripts + their tests — that is the product.
- `docs/discussion/`, `docs/prism-all/` review provenance — audit trail (PRD §13),
  kept. `docs/PRD.md`, `M0-PLAN.md`, `VS-INSANE-RESEARCH.md`, `ADOPTION-PLAN.md`,
  `NEXT-SESSION.md` — current, kept.

## Net effect
Removing the shadow §6.7 logic makes "`validate_ledger.py` is the SOLE joiner" a
property of the codebase, not just the docs — there is no longer a second status
classifier to drift out of sync.
