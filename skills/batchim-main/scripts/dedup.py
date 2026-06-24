#!/usr/bin/env python3
"""dedup.py — 받침 independence partition (PRD §6.2 FR-I0).

M1: canonical-URL + normalized-text simhash/shingle + publication-time
clustering -> frozen independence_partition.json (source_id -> cluster_id),
deterministic (stable tiebreak by source_id). Source set frozen at end of
Phase 3.5. M3 (FR-I1): semantic near-dup, distinguishing content near-dup from
provenance dependence. TODO (M1b).
"""
raise NotImplementedError("dedup.py: implement per PRD §6.2 (M1b)")
