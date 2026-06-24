#!/usr/bin/env python3
"""Tests for 받침 lock.py (NFR-4 single-session lock + heartbeat). Run: python tests/test_lock.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "batchim-main", "scripts"))
import lock  # noqa: E402

P = F = 0
DEAD = lambda p, t: False
ALIVE = lambda p, t: True


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    d = tempfile.mkdtemp(prefix="batchim_lock_")
    ok, _ = lock.acquire(d, pid=100, start_token="t100", now=1000.0)
    check("acquire fresh -> ok", ok)

    # same holder reacquires / heartbeats
    check("heartbeat by holder -> ok", lock.heartbeat(d, 100, "t100", now=1010.0))
    ok, why = lock.acquire(d, 100, "t100", now=1020.0)
    check("reacquire by same holder", ok and why == "reacquired")

    # another live session is refused
    ok, _ = lock.acquire(d, pid=200, start_token="t200", now=1030.0, pid_alive=ALIVE)
    check("live other -> refused", not ok)
    check("heartbeat by non-holder -> false", not lock.heartbeat(d, 200, "t200", now=1031.0))

    # stale AND alive -> still refused without force
    ok, why = lock.acquire(d, 200, "t200", now=1000.0 + lock.DEFAULT_TTL + 100, pid_alive=ALIVE)
    check("stale+alive -> refuse (force needed)", not ok and "force" in why)

    # stale AND dead -> reclaimable
    ok, why = lock.acquire(d, 200, "t200", now=1000.0 + lock.DEFAULT_TTL + 100, pid_alive=DEAD)
    check("stale+dead -> reclaimed", ok and why == "reclaimed")

    # PID reuse defense: same pid number, different start_token, live -> NOT the holder
    lock.acquire(d, pid=300, start_token="boot-A", now=2000.0)
    ok, _ = lock.acquire(d, pid=300, start_token="boot-B", now=2010.0, pid_alive=ALIVE)
    check("PID reuse (diff start_token) -> refused as other", not ok)

    # force overrides a live lock
    ok, why = lock.acquire(d, pid=400, start_token="t400", now=2020.0, pid_alive=ALIVE, force=True)
    check("force -> acquired over live lock", ok)

    # release only by holder, then re-acquire is fresh
    check("release by non-holder -> false", not lock.release(d, 999, "x"))
    check("release by holder -> true", lock.release(d, 400, "t400"))
    ok, why = lock.acquire(d, 500, "t500", now=2030.0)
    check("after release -> fresh acquire", ok and why == "acquired")

    # is_stale reflects heartbeat age
    check("is_stale: fresh -> False", not lock.is_stale(d, now=2031.0))
    check("is_stale: aged -> True", lock.is_stale(d, now=2030.0 + lock.DEFAULT_TTL + 1))


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
