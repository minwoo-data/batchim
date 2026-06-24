# Baseline (M0 0.3)

`insane-research` baseline metrics on the frozen `bench/topics.json`, recorded
BEFORE any 받침 tuning, hashed into the signed manifest (PRD FR-S1). For each
topic: leak_rate, citation_resolution_rate, and human-labeled false-entail rate
per failure-mode stratum. These are the numbers 받침 must beat (PRD G3/§9).

Status: TODO — run upstream insane-research on the frozen topics and store
`<topic_id>.json` per run.
