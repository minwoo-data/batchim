#!/usr/bin/env python3
"""entail_gate.py — 받침 isolated-verifier entailment gate (PRD §6.3, App B).

For each high-risk ATOMIC claim x cited span, spawn a FRESH isolated subagent
given only (atomic_claim, span+context, source_text) and force structured
output {label, evidence_span, ...}. Then apply mechanical anchors IN CODE:
  1. verbatim span-match against the frozen snapshot (Appendix B normalization)
  2. numeric/date/unit consistency
anchors_ok := span_matched AND numeric_ok. Anchors apply symmetrically to
entails and contradicts. Writes gate-owned entailment_verdicts.jsonl, each row
bound to claim_text_hash + snapshot_hash + verifier_prompt_hash + model_id.

The subagent spawn is orchestrated by SKILL.md (prompt) per the data-flow lock;
this script handles anchor checks + verdict persistence. TODO (M1a).
"""
raise NotImplementedError("entail_gate.py: implement per PRD §6.3 (M1a)")
