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


# --- cost model: pre-launch $/tokens-per-run estimate -----------------------
# Nobody adopts a research tool without a "$ per run" number. A run's LLM cost is
# dominated by two fan-outs (PRD §6.3/§6.8):
#   verifier_calls = 1 isolated verifier per cited (claim, source) ref
#   panel_calls    = 3 prompt-diverse lenses per verified-CANDIDATE claim
# Token sizing is per-call; the big input is the source SNAPSHOT the verifier reads
# and the cited context the panel lens reads. Defaults are order-of-magnitude — a
# deployment overrides them with measured medians. NO LLM here; pure arithmetic.

import math  # noqa: E402

N_PANEL_LENSES = 3  # refute / source_quality / numeric_consistency (panel.LENSES)

# per-call token sizing (override per deployment with measured medians)
DEFAULT_SIZING = {
    "verifier_prompt_overhead": 600,   # system + isolation instructions + schema
    "claim_tokens": 60,                # the atomic claim text
    "snapshot_tokens": 1200,           # fetched source text the verifier must read (dominant)
    "verifier_output": 250,            # verdict + rationale + span coords
    "panel_prompt_overhead": 700,      # lens-specific adversarial instructions
    "panel_context_tokens": 1500,      # claim + its cited spans/sources the lens reviews
    "panel_output": 300,               # vote + rationale
}

# illustrative price per 1M tokens (USD). OVERRIDE with current pricing — these are
# placeholders, not a live quote. Pass price_in/price_out to estimate_cost to be exact.
ILLUSTRATIVE_PRICE = {"in_per_mtok": 3.0, "out_per_mtok": 15.0}


def estimate_calls(n_high_risk_claims, sources_per_claim=2.0,
                   panel_candidate_frac=1.0):
    """LLM call counts for a run, honoring the NFR-1 caps. `panel_candidate_frac`
    is the share of high-risk claims that survive to the panel (anchored + enough
    independent entails to be a verified-candidate). Returns counts + whether a cap
    clipped the run (→ completed-degraded)."""
    raw_verifier = max(0, round(n_high_risk_claims * sources_per_claim))
    verifier = min(raw_verifier, MAX_VERIFIER_CALLS)
    candidates = math.ceil(max(0, n_high_risk_claims) * panel_candidate_frac)
    raw_panel = candidates * N_PANEL_LENSES
    panel = min(raw_panel, MAX_PANEL_CALLS)
    return {
        "verifier_calls": verifier,
        "panel_calls": panel,
        "panel_candidates": candidates,
        "total_calls": verifier + panel,
        "verifier_capped": raw_verifier > MAX_VERIFIER_CALLS,
        "panel_capped": raw_panel > MAX_PANEL_CALLS,
    }


def estimate_tokens(calls, sizing=None):
    """Input/output tokens from call counts. Verifier input = overhead+claim+snapshot;
    panel input = overhead+context. Returns a breakdown + totals."""
    s = {**DEFAULT_SIZING, **(sizing or {})}
    v = calls["verifier_calls"]
    p = calls["panel_calls"]
    v_in = v * (s["verifier_prompt_overhead"] + s["claim_tokens"] + s["snapshot_tokens"])
    v_out = v * s["verifier_output"]
    p_in = p * (s["panel_prompt_overhead"] + s["panel_context_tokens"])
    p_out = p * s["panel_output"]
    return {
        "verifier_input": v_in, "verifier_output": v_out,
        "panel_input": p_in, "panel_output": p_out,
        "input_tokens": v_in + p_in, "output_tokens": v_out + p_out,
        "total_tokens": v_in + p_in + v_out + p_out,
    }


def estimate_cost(tokens, price_in_per_mtok=None, price_out_per_mtok=None):
    """USD cost from token totals. Defaults to ILLUSTRATIVE_PRICE (placeholder) —
    pass current per-MTok prices for an accurate quote. Returns dict with usd + the
    price used (so the caller can see whether it was the placeholder)."""
    pin = ILLUSTRATIVE_PRICE["in_per_mtok"] if price_in_per_mtok is None else price_in_per_mtok
    pout = ILLUSTRATIVE_PRICE["out_per_mtok"] if price_out_per_mtok is None else price_out_per_mtok
    usd = tokens["input_tokens"] / 1e6 * pin + tokens["output_tokens"] / 1e6 * pout
    return {"usd": round(usd, 4), "price_in_per_mtok": pin, "price_out_per_mtok": pout,
            "illustrative": price_in_per_mtok is None and price_out_per_mtok is None}


def estimate_run(n_high_risk_claims, sources_per_claim=2.0, panel_candidate_frac=1.0,
                 sizing=None, price_in_per_mtok=None, price_out_per_mtok=None):
    """One-shot pre-launch estimate: calls → tokens → cost. Returns the full bundle."""
    calls = estimate_calls(n_high_risk_claims, sources_per_claim, panel_candidate_frac)
    tokens = estimate_tokens(calls, sizing)
    cost = estimate_cost(tokens, price_in_per_mtok, price_out_per_mtok)
    return {"inputs": {"n_high_risk_claims": n_high_risk_claims,
                       "sources_per_claim": sources_per_claim,
                       "panel_candidate_frac": panel_candidate_frac},
            "calls": calls, "tokens": tokens, "cost": cost}


def format_estimate(est):
    """Human pre-launch line for SKILL.md to print before dispatching the fan-out."""
    c, t, m = est["calls"], est["tokens"], est["cost"]
    cap = []
    if c["verifier_capped"]:
        cap.append(f"verifier capped at {MAX_VERIFIER_CALLS}")
    if c["panel_capped"]:
        cap.append(f"panel capped at {MAX_PANEL_CALLS}")
    cap_s = f"  [DEGRADED: {', '.join(cap)}]" if cap else ""
    price_s = " (illustrative price - override)" if m["illustrative"] else ""
    return (f"batchim cost estimate - {est['inputs']['n_high_risk_claims']} high-risk claims:\n"
            f"  LLM calls: {c['total_calls']}  "
            f"(verifier {c['verifier_calls']} + panel {c['panel_calls']} "
            f"= 3x{c['panel_candidates']} candidates)\n"
            f"  tokens: {t['total_tokens']:,} "
            f"(in {t['input_tokens']:,} / out {t['output_tokens']:,})\n"
            f"  est. cost: ${m['usd']:.2f}{price_s}{cap_s}")


def main():
    import argparse
    p = argparse.ArgumentParser(description="받침 pre-launch cost estimate")
    p.add_argument("--claims", type=int, required=True, help="# high-risk atomic claims")
    p.add_argument("--sources-per-claim", type=float, default=2.0)
    p.add_argument("--panel-frac", type=float, default=1.0,
                   help="share of high-risk claims reaching the panel (0..1)")
    p.add_argument("--price-in", type=float, help="USD per 1M input tokens")
    p.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    a = p.parse_args()
    est = estimate_run(a.claims, a.sources_per_claim, a.panel_frac,
                       price_in_per_mtok=a.price_in, price_out_per_mtok=a.price_out)
    print(format_estimate(est))


if __name__ == "__main__":
    main()
