#!/usr/bin/env python3
"""budget.py — 받침 fan-out throttle + reserve-before-dispatch budget (PRD §6.8
FR-P2, NFR-1).

Caps the verifier/panel fan-out so a run can't blow the cost ceiling, and enforces
**reserve-before-dispatch**: a worker must `reserve()` a slot BEFORE it dispatches
an LLM call, so N concurrent workers can never each see "budget = 1" and all fire
(the classic over-dispatch race). In the single-OS-process async orchestration
(NG3) reserve() is a check-and-decrement that is atomic w.r.t. the event loop.

Cap-exhaustion is NOT an error: the run finalizes **completed-degraded** (FR-X3),
with the unreserved spans forced to `unresolved (skipped_budget)` so an unqueried
`contradicts` can never be skipped into a false `verified` (NFR-1).
"""

# NFR-1 default caps
MAX_VERIFIER_CALLS = 120
MAX_PANEL_CALLS = 90          # ~3 lenses * verified-candidates
MAX_SPANS_PER_CLAIM = 3
MAX_CONCURRENT = 3            # throttle: 2–3 concurrent (subscription rate-limit guard)


class Budget:
    """A reserve-before-dispatch counter. `reserve(n)` succeeds only if the whole
    request fits, decrementing atomically; otherwise it fails WITHOUT partial
    spend (so a caller that can't fully reserve degrades cleanly)."""

    def __init__(self, total):
        if total < 0:
            raise ValueError("budget total must be >= 0")
        self._total = total
        self._remaining = total
        self._exhausted = False

    def reserve(self, n=1):
        """Atomically reserve n slots. Returns True if granted. A denied reserve
        marks the budget exhausted (→ completed-degraded)."""
        if n <= 0:
            return True
        if self._remaining >= n:
            self._remaining -= n
            return True
        self._exhausted = True
        return False

    def release(self, n=1):
        """Return slots from a call that failed before dispatch (retry budget is
        separate; releasing never exceeds the original total)."""
        self._remaining = min(self._total, self._remaining + max(0, n))

    def remaining(self):
        return self._remaining

    def spent(self):
        return self._total - self._remaining

    @property
    def exhausted(self):
        return self._exhausted


def cap_concurrency(requested):
    """Clamp a requested fan-out width to the throttle ceiling (FR-P2)."""
    return max(1, min(requested, MAX_CONCURRENT))
