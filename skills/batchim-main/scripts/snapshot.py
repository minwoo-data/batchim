#!/usr/bin/env python3
"""snapshot.py — 받침 source snapshotting (PRD §6.5 FR-S1, §6.2).

Freeze each fetched source's text + content_hash so entailment runs against an
immutable snapshot (not the live web), making span-matches auditable and replay
reproducible. TODO (M1a): implement fetch->normalize->store->hash; write
snapshot_path + content_hash back into sources.jsonl.
"""
raise NotImplementedError("snapshot.py: implement per PRD §6.5 (M1a)")
