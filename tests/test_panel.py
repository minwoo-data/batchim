#!/usr/bin/env python3
"""Tests for 받침 panel.py: 2-of-3 consensus, quarantine on split/missing/failed.
Run: python tests/test_panel.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import panel  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def test_consensus():
    check("3 entails -> entails", panel.consensus(["entails"] * 3) == "entails")
    check("2 entails 1 contra -> entails", panel.consensus(["entails", "entails", "contradicts"]) == "entails")
    check("2 contra 1 entails -> contradicts", panel.consensus(["contradicts", "contradicts", "entails"]) == "contradicts")
    check("1-1-1 split -> no_consensus", panel.consensus(["entails", "neutral", "contradicts"]) == "no_consensus")
    check("<3 valid votes -> no_consensus", panel.consensus(["entails", "entails"]) == "no_consensus")
    check("invalid votes dropped -> no_consensus", panel.consensus(["entails", "entails", "bogus"]) == "no_consensus")


def _lv(refute, sq, num, states=None, models=None):
    states = states or {}
    models = models or {}
    out = {}
    for lens, vote in (("refute", refute), ("source_quality", sq), ("numeric_consistency", num)):
        if vote is not None:
            row = {"vote": vote, "vote_state": states.get(lens, "done")}
            if lens in models:
                row["model_id"] = models[lens]
            out[lens] = row
    return out


def test_model_diversity():
    # assign_lenses spreads lenses across distinct models (round-robin)
    a = panel.assign_lenses(["claude", "codex"])
    check("assign: uses both models", set(a.values()) == {"claude", "codex"})
    check("assign: deterministic", a == panel.assign_lenses(["codex", "claude"]))
    check("assign: one model -> all on it", set(panel.assign_lenses(["claude"]).values()) == {"claude"})

    # panel verdict records model diversity
    mv = {"refute": "claude", "source_quality": "codex", "numeric_consistency": "claude"}
    r = panel.panel_verdict("c", _lv("entails", "entails", "entails", models=mv))
    check("verdict: 2 distinct models", r["n_models"] == 2 and r["model_diverse"] is True)
    check("verdict: vote_models recorded", r["vote_models"]["source_quality"] == "codex")

    # all same model -> not model-diverse (correlated-error caveat applies)
    same = {"refute": "claude", "source_quality": "claude", "numeric_consistency": "claude"}
    r = panel.panel_verdict("c", _lv("entails", "entails", "entails", models=same))
    check("verdict: single model -> not diverse", r["n_models"] == 1 and r["model_diverse"] is False)

    # diversity is metadata, not a gate: consensus is unchanged by it
    check("verdict: consensus still entails regardless of diversity", r["panel_consensus"] == "entails")


def test_panel_verdict():
    r = panel.panel_verdict("c", _lv("entails", "entails", "entails"))
    check("all entails -> entails", r["panel_consensus"] == "entails" and r["n_valid"] == 3)

    r = panel.panel_verdict("c", _lv("contradicts", "neutral", "entails"))
    check("1-1-1 -> no_consensus", r["panel_consensus"] == "no_consensus")

    # quote-mine: refute lens catches it, others entail -> 2-of-3 entails still
    r = panel.panel_verdict("c", _lv("contradicts", "contradicts", "entails"))
    check("2 contradicts -> contradicts (quarantine)", r["panel_consensus"] == "contradicts")

    # missing lens -> quarantine
    r = panel.panel_verdict("c", _lv("entails", "entails", None))
    check("missing lens -> no_consensus", r["panel_consensus"] == "no_consensus" and r["missing_lenses"] == ["numeric_consistency"])

    # failed lens -> quarantine
    r = panel.panel_verdict("c", _lv("entails", "entails", "entails", states={"refute": "failed"}))
    check("failed lens -> no_consensus", r["panel_consensus"] == "no_consensus" and r["failed_lenses"] == ["refute"])


if __name__ == "__main__":
    test_consensus()
    test_panel_verdict()
    test_model_diversity()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
