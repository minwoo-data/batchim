#!/usr/bin/env python3
"""Tests for dedup.py independence partition (PRD §6.2 FR-I0, Gap B).
Run: python tests/test_dedup.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "skills", "batchim-main", "scripts"))
import dedup  # noqa: E402

P = F = 0


def check(name, cond):
    global P, F
    if cond:
        P += 1
    else:
        F += 1
        print(f"  FAIL: {name}")


def run():
    # canonical url: strip www + tracking params, sort query, force https
    check("canonical strips www/tracking",
          dedup.canonical_url("http://www.x.com/a/?utm_source=z&id=5") == "https://x.com/a?id=5")

    syndicated = "The agency approved the merger after a lengthy antitrust review process."
    srcs = [
        {"id": "s1", "url": "https://apnews.com/article/foo?utm_source=x", "snippet": syndicated},
        {"id": "s2", "url": "https://www.reuters.com/business/foo", "snippet": syndicated},
        {"id": "s3", "url": "https://ft.com/content/bar",
         "snippet": "Critics argue the deal will reduce competition and raise consumer prices sharply."},
    ]
    part = dedup.partition(srcs)
    check("Gap B: syndicated copies collapse", part["s1"] == part["s2"])
    check("Gap B: independent source separate", part["s3"] != part["s1"])
    check("Gap B: 2 clusters total", len(set(part.values())) == 2)

    # determinism: same input -> same partition regardless of input order
    p2 = dedup.partition(list(reversed(srcs)))
    check("deterministic across input order", part == p2)

    # exact-duplicate canonical URL collapses even with different snippets
    same_url = [
        {"id": "a", "url": "https://x.com/p?id=1&utm_source=q", "snippet": "alpha beta gamma"},
        {"id": "b", "url": "https://x.com/p?id=1", "snippet": "totally different words here entirely"},
    ]
    pu = dedup.partition(same_url)
    check("same canonical-URL collapses", pu["a"] == pu["b"])

    # empty-text guard: distinct-URL sources with NO text must NOT collapse
    # (regression: empty simhash=0 for all -> hamming 0 -> false near-dup merge)
    no_text = [
        {"id": "n1", "url": "https://rfc-editor.org/rfc/rfc9001"},
        {"id": "n2", "url": "https://rfc-editor.org/rfc/rfc9114"},
        {"id": "n3", "url": "https://example.dev/blog"},
    ]
    pn = dedup.partition(no_text)
    check("empty-text: distinct URLs stay separate", len(set(pn.values())) == 3)

    # `text` field (Appendix A schema) drives the simhash signal
    txt = [
        {"id": "t1", "url": "https://a.com/1", "text": "Clients MUST NOT offer TLS versions older than 1.3."},
        {"id": "t2", "url": "https://b.com/2", "text": "QUIC version 1 uses TLS version 1.3 or greater as its handshake protocol."},
    ]
    pt = dedup.partition(txt)
    check("text field: distinct content stays separate", pt["t1"] != pt["t2"])


if __name__ == "__main__":
    run()
    print(f"\n{P} passed, {F} failed")
    sys.exit(1 if F else 0)
