#!/usr/bin/env python3
"""snapshot.py — 받침 source snapshotting (PRD §6.5 FR-S1, §6.2; Appendix A).

Freeze each fetched source's text into an immutable on-disk snapshot + content
hash so entailment runs against a frozen snapshot (not the live web). This makes
verbatim span-matches auditable (anchors.span_match normalizes snapshot+span at
compare time) and replay reproducible (FR-S1: the manifest signs ordered
`{source_id, snapshot_path, snapshot_hash}`, exactly one snapshot per source).

Separation of concerns (deliberate):
  - The snapshot stored on disk is the *faithful* fetched text (only line-endings
    normalized for cross-platform-stable hashing). It is NOT Appendix-B folded —
    keeping it auditable. Appendix-B normalization is applied at *match time* by
    anchors.normalize(), identically to span and snapshot.
  - `content_hash` (sources.jsonl) IS the `snapshot_hash` that verdicts bind to
    (entailment_verdicts.snapshot_hash; FR-A5 binding integrity). Same source ⇒
    same value.

Input text per source (first available wins):
  1. inline  `text`        field on the source row, or
  2. `raw_path` / `snapshot_path` pointing at a UTF-8 text file (relative to the
     session dir or absolute).
A source with no obtainable text is a hard error (exit 2): the "every source has
exactly one frozen snapshot" invariant cannot hold otherwise.

Input/Output: <session>/sources/sources.jsonl  (rewritten in place with
`snapshot_path` + `content_hash` set; inline `text` dropped once frozen).
Snapshots: <session>/snapshots/<source_id>.txt
"""

import argparse
import hashlib
import json
import os

SNAPSHOT_VERSION = "0.1.0-m1a"


# --- pure helpers (no I/O) --------------------------------------------------
def canonical_text(text: str) -> str:
    """Faithful text with line-endings normalized to \\n (cross-platform-stable
    hashing). No Appendix-B folding here — the snapshot stays auditable; folding
    happens at match time (anchors.normalize)."""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_hash(text: str) -> str:
    """sha256 over the UTF-8 bytes of the canonical snapshot text. Prefixed
    `sha256:` to match Appendix A (`content_hash`/`snapshot_hash`)."""
    h = hashlib.sha256(canonical_text(text).encode("utf-8")).hexdigest()
    return f"sha256:{h}"


# --- I/O --------------------------------------------------------------------
def _read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rows.append((i, json.loads(line)))
    return rows


def _source_text(src, session):
    """Resolve a source's raw text from inline `text` or a `raw_path`/
    `snapshot_path` file. Returns (text, origin) or (None, reason)."""
    if isinstance(src.get("text"), str):
        return src["text"], "inline"
    for key in ("raw_path", "snapshot_path"):
        rel = src.get(key)
        if not rel:
            continue
        path = rel if os.path.isabs(rel) else os.path.join(session, rel)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return f.read(), key
        return None, f"{key} points at missing file: {rel}"
    return None, "no inline 'text' and no raw_path/snapshot_path"


def freeze(session, sources_path=None, snap_dir=None):
    """Freeze every source. Idempotent: a source already pointing at a snapshot
    whose on-disk hash still matches `content_hash` is left untouched. Returns
    (rows_out, errors)."""
    sources_path = sources_path or os.path.join(session, "sources", "sources.jsonl")
    snap_dir = snap_dir or os.path.join(session, "snapshots")
    os.makedirs(snap_dir, exist_ok=True)

    rows = _read_jsonl(sources_path)
    out, errors, seen = [], [], set()

    for i, src in rows:
        sid = src.get("id")
        if not sid:
            errors.append(f"sources.jsonl[{i}]: missing 'id'")
            out.append(src)
            continue
        if sid in seen:
            errors.append(f"sources.jsonl[{i}]: duplicate source id '{sid}'")
            out.append(src)
            continue
        seen.add(sid)

        snap_path = os.path.join(snap_dir, f"{sid}.txt")
        # POSIX-normalized relative path: the manifest signs snapshot_path
        # (FR-S1), so it must be byte-identical across platforms.
        rel_path = os.path.relpath(snap_path, session).replace(os.sep, "/")

        # Idempotent skip: existing snapshot whose hash still matches.
        if (src.get("snapshot_path") and src.get("content_hash")
                and os.path.isfile(snap_path)):
            with open(snap_path, encoding="utf-8") as f:
                if content_hash(f.read()) == src["content_hash"]:
                    src.pop("text", None)
                    out.append(src)
                    continue

        text, origin = _source_text(src, session)
        if text is None:
            errors.append(f"source '{sid}': {origin}")
            out.append(src)
            continue

        canon = canonical_text(text)
        with open(snap_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(canon)

        src["snapshot_path"] = rel_path
        src["content_hash"] = content_hash(canon)
        src["snapshot_version"] = SNAPSHOT_VERSION
        src.setdefault("fetched_at", src.get("fetched_at"))
        src.pop("text", None)  # frozen now; drop inline copy
        out.append(src)

    return out, errors


def _write_jsonl(path, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)  # atomic temp-then-rename (NFR-4)


def main():
    p = argparse.ArgumentParser(description="받침 source snapshotting (freeze + hash)")
    p.add_argument("--session", required=True, help="session folder")
    p.add_argument("--sources", help="sources.jsonl path (override)")
    p.add_argument("--snapshots", help="snapshots dir (override)")
    args = p.parse_args()

    sources_path = args.sources or os.path.join(args.session, "sources", "sources.jsonl")
    rows, errors = freeze(args.session, sources_path, args.snapshots)

    if errors:
        for e in errors:
            print(f"snapshot: ERROR {e}")
        # Every source must have exactly one frozen snapshot — fail structurally.
        raise SystemExit(2)

    _write_jsonl(sources_path, rows)
    print(f"snapshot: froze {len(rows)} sources -> {sources_path}")


if __name__ == "__main__":
    main()
