#!/usr/bin/env python3
"""commit.py — 받침 single-rename commit (PRD §6.5 FR-S3; M1b durability).

The ONLY atomic commit point of a run. Decisions + signed manifest are first
written to a **staging dir**; the run becomes durable only when (a) the staging
dir is renamed to the content-addressed `runs/<run_id>/`, and (b) the `CURRENT`
pointer is atomically replaced to name that run_id. On startup we **trust only
`CURRENT → run_id` whose manifest verifies byte-for-byte**; a leftover `.staging`
(crash mid-commit) is discarded — roll-forward only on full verify.

Lock/heartbeat live elsewhere (not in the committed record). run_id is derived
from the manifest signature (content-addressed) so re-committing identical content
is idempotent.
"""

import json
import os
import shutil

import manifest as mf

_OUTPUT_FILES = ("verified_claims.json", "unresolved_claims.json",
                 "refuted_claims.json", "manifest.json")


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def commit_run(session, man, source_dir=None):
    """Stage the run's outputs + manifest into runs/<run_id>/ and flip CURRENT.
    `source_dir` defaults to <session>/outputs (the working copy already written).
    Returns run_id. The CURRENT replace is the sole atomic commit point (FR-S3)."""
    run_id = man["run_id"]
    runs = os.path.join(session, "runs")
    staging = os.path.join(runs, ".staging")
    target = os.path.join(runs, run_id)
    src = source_dir or os.path.join(session, "outputs")
    os.makedirs(runs, exist_ok=True)

    # discard any leftover incomplete staging (crash recovery)
    if os.path.isdir(staging):
        shutil.rmtree(staging, ignore_errors=True)

    if os.path.isdir(target):
        # content-addressed: an existing run_id is byte-identical. Idempotent —
        # don't re-stage; just (re)point CURRENT.
        pass
    else:
        os.makedirs(staging)
        for fn in _OUTPUT_FILES:
            sp = os.path.join(src, fn)
            if os.path.isfile(sp):
                shutil.copyfile(sp, os.path.join(staging, fn))
        os.replace(staging, target)        # atomic dir rename → run becomes durable

    # the SOLE atomic commit point: flip CURRENT to this run_id
    _atomic_write(os.path.join(session, "CURRENT"),
                  json.dumps({"run_id": run_id, "signature": man["signature"]}, ensure_ascii=False))
    return run_id


def read_current(session):
    """Resolve CURRENT → the committed run dir, verifying byte-for-byte. Returns
    (run_dir, manifest). Raises ValueError if absent / incomplete / tampered
    (caller maps to exit 2; FR-S3 "trust only what verifies")."""
    cur_path = os.path.join(session, "CURRENT")
    if not os.path.isfile(cur_path):
        raise ValueError("CURRENT absent — no committed run")
    cur = json.load(open(cur_path, encoding="utf-8"))
    run_dir = os.path.join(session, "runs", cur["run_id"])
    man_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(man_path):
        raise ValueError(f"CURRENT → {cur['run_id']} but its manifest is missing (incomplete commit)")
    man = json.load(open(man_path, encoding="utf-8"))

    if man.get("signature") != cur.get("signature"):
        raise ValueError("CURRENT signature ≠ committed manifest signature")
    if mf.sign(man) != man.get("signature"):
        raise ValueError("committed manifest body does not match its signature (tampered)")
    if man.get("run_id") != cur["run_id"]:
        raise ValueError("committed manifest run_id ≠ CURRENT run_id")
    # byte-for-byte: re-hash the committed output files against the manifest
    for key, fn in (("verified_claims", "verified_claims.json"),
                    ("unresolved_claims", "unresolved_claims.json"),
                    ("refuted_claims", "refuted_claims.json")):
        want = man["output_hashes"].get(key)
        got = mf.file_hash(os.path.join(run_dir, fn))
        if want != got:
            raise ValueError(f"committed {fn} drift (want {want}, got {got})")
    return run_dir, man
