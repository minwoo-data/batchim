#!/usr/bin/env python3
"""panel.py — 받침 N=3 verification panel (PRD §6.8 FR-P1/P3) — IN MVP.

Per high-risk/contested claim, run N=3 prompt-diverse lenses
(refute / source-quality / numeric-consistency), model/config-diverse where
available. Consensus = 2-of-3; a 1-1-1 split or any missing/failed vote ->
quarantine (unresolved). Panel verdicts (producer=panel) supersede the single
verifier per (claim,source); a refutation override is a claim-level re-vote.
This is the quote-mining defense and is part of the MVP. TODO (M2).
"""
raise NotImplementedError("panel.py: implement per PRD §6.8 (M2)")
