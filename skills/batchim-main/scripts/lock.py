#!/usr/bin/env python3
"""lock.py — 받침 single-session lock + heartbeat (PRD NFR-4).

A research session is single-session (NG3). The lock is acquired before Phase 1 and
lives in a SEPARATE file from the committed run record (FR-S3), so a crashed run
leaves a stale lock but never a half-committed `CURRENT`.

Lock record = {pid, start_token, heartbeat_ts}. "PID alive" means same pid AND same
start_token (start-time / boot nonce) — this defends against PID reuse. Reclaim ONLY
when the heartbeat is stale AND the PID is dead; `stale AND alive` ⇒ refuse + --force
(a live run we can't prove is gone). Deterministic: clock + pid-liveness are injected.
"""

import json
import os

DEFAULT_TTL = 90.0   # seconds; a live holder must heartbeat within this


def _path(session):
    return os.path.join(session, "LOCK")


def _read(session):
    p = _path(session)
    if not os.path.isfile(p):
        return None
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def acquire(session, pid, start_token, now, ttl=DEFAULT_TTL, force=False, pid_alive=None):
    """Try to take the lock. Returns (ok, reason). `pid_alive(pid, start_token)->bool`
    decides liveness (defaults to "assume alive" — conservative, never reclaims a lock
    it can't prove dead). `now` is the current time (injected for determinism)."""
    pid_alive = pid_alive or (lambda p, t: True)
    cur = _read(session)
    if cur is not None and not (cur.get("pid") == pid and cur.get("start_token") == start_token):
        alive = pid_alive(cur.get("pid"), cur.get("start_token"))
        stale = (now - cur.get("heartbeat_ts", 0)) > ttl
        if not force:
            if alive:
                return (False, "held by a live session" + (" (stale heartbeat — use --force)" if stale else ""))
            if not stale:
                return (False, "held by a dead PID with a fresh heartbeat — use --force")
            # not alive AND stale ⇒ reclaimable
    _atomic_write(_path(session), {"pid": pid, "start_token": start_token, "heartbeat_ts": now})
    return (True, "acquired" if cur is None else ("reacquired" if cur.get("pid") == pid else "reclaimed"))


def heartbeat(session, pid, start_token, now):
    """Refresh the heartbeat IFF we still hold the lock. Returns ok."""
    cur = _read(session)
    if not cur or cur.get("pid") != pid or cur.get("start_token") != start_token:
        return False
    _atomic_write(_path(session), {"pid": pid, "start_token": start_token, "heartbeat_ts": now})
    return True


def release(session, pid, start_token):
    """Release the lock IFF we hold it. Returns ok."""
    cur = _read(session)
    if cur and cur.get("pid") == pid and cur.get("start_token") == start_token:
        try:
            os.remove(_path(session))
        except OSError:
            pass
        return True
    return False


def is_stale(session, now, ttl=DEFAULT_TTL):
    cur = _read(session)
    return cur is not None and (now - cur.get("heartbeat_ts", 0)) > ttl
