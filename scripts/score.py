#!/usr/bin/env python3
"""
score.py — Scoring operations.

This is primarily a query/aggregation layer on top of the SQLite DB.
Actual scoring judgments live in YAML; this script computes:

- Weighted composite scores per entity
- Gap reports (entities missing scores on a dimension)
- Score drift detection (comparing to scores_history)

Usage:
    python scripts/score.py summary                 # show composite scores for all entities
    python scripts/score.py gaps                    # show missing-score gaps
    python scripts/score.py platform <id>           # show scores for one platform
    python scripts/score.py asset <id>              # show scores for one asset

Design principle: scoring JUDGMENTS live in YAML. This script does not
originate scores — it aggregates and reports on them.
"""

import sys
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "lai.db"

# Weights for composite score computation. Tunable per the scoring rubric.
# Sum should be 1.0.
PLATFORM_WEIGHTS = {
    "tech": 0.40,
    "ip": 0.30,
    "dealability": 0.30,
}
ASSET_WEIGHTS = {
    "tech": 0.20,
    "clinical": 0.30,
    "ip": 0.15,
    "dealability": 0.20,
    "regulatory": 0.15,
}


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}. Run: python scripts/build_db.py", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def composite(scores: dict, weights: dict) -> float | None:
    """Compute weighted composite. Returns None if any dimension is missing."""
    if not all(d in scores for d in weights):
        return None
    return round(sum(scores[d] * w for d, w in weights.items()), 2)


def platform_scores(conn, platform_id: str) -> dict:
    cur = conn.execute("""
        SELECT dimension, value, rationale, confidence, scorer, scored_at
        FROM scores WHERE entity_type='platform' AND entity_id=?
    """, (platform_id,))
    return {r["dimension"]: dict(r) for r in cur.fetchall()}


def asset_scores(conn, asset_id: str) -> dict:
    cur = conn.execute("""
        SELECT dimension, value, rationale, confidence, scorer, scored_at, inherited_from
        FROM scores WHERE entity_type='asset' AND entity_id=?
    """, (asset_id,))
    return {r["dimension"]: dict(r) for r in cur.fetchall()}


def cmd_summary(conn):
    print("\nPLATFORM COMPOSITE SCORES")
    print("-" * 70)
    print(f"{'Platform':<18}{'Tech':>6}{'IP':>6}{'Deal':>6}{'Composite':>12}")
    print("-" * 70)
    for row in conn.execute("SELECT id, name FROM platforms ORDER BY id"):
        s = platform_scores(conn, row["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, PLATFORM_WEIGHTS)
        comp_str = f"{comp:.2f}" if comp is not None else "incomplete"
        print(f"{row['name']:<18}"
              f"{vals.get('tech', '-'):>6}"
              f"{vals.get('ip', '-'):>6}"
              f"{vals.get('dealability', '-'):>6}"
              f"{comp_str:>12}")

    print("\nASSET COMPOSITE SCORES")
    print("-" * 80)
    print(f"{'Asset':<14}{'Tech':>6}{'Clin':>6}{'IP':>6}{'Deal':>6}{'Reg':>6}{'Composite':>12}")
    print("-" * 80)
    for row in conn.execute("SELECT id, name FROM assets ORDER BY id"):
        s = asset_scores(conn, row["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, ASSET_WEIGHTS)
        comp_str = f"{comp:.2f}" if comp is not None else "incomplete"
        print(f"{row['name']:<14}"
              f"{vals.get('tech', '-'):>6}"
              f"{vals.get('clinical', '-'):>6}"
              f"{vals.get('ip', '-'):>6}"
              f"{vals.get('dealability', '-'):>6}"
              f"{vals.get('regulatory', '-'):>6}"
              f"{comp_str:>12}")


def cmd_gaps(conn):
    print("\nPLATFORM SCORE GAPS")
    for row in conn.execute("SELECT id, name FROM platforms ORDER BY id"):
        s = platform_scores(conn, row["id"])
        missing = set(PLATFORM_WEIGHTS) - set(s)
        low_conf = [d for d, v in s.items() if v["confidence"] == "low"]
        if missing or low_conf:
            print(f"  {row['name']}:")
            if missing:
                print(f"    missing dimensions: {sorted(missing)}")
            if low_conf:
                print(f"    low-confidence:     {sorted(low_conf)}")

    print("\nASSET SCORE GAPS")
    for row in conn.execute("SELECT id, name FROM assets ORDER BY id"):
        s = asset_scores(conn, row["id"])
        missing = set(ASSET_WEIGHTS) - set(s)
        low_conf = [d for d, v in s.items() if v["confidence"] == "low"]
        if missing or low_conf:
            print(f"  {row['name']}:")
            if missing:
                print(f"    missing dimensions: {sorted(missing)}")
            if low_conf:
                print(f"    low-confidence:     {sorted(low_conf)}")


def cmd_detail(conn, entity_type: str, entity_id: str):
    fn = platform_scores if entity_type == "platform" else asset_scores
    s = fn(conn, entity_id)
    if not s:
        print(f"No scores found for {entity_type}:{entity_id}", file=sys.stderr)
        sys.exit(1)
    print(f"\n{entity_type.upper()} {entity_id} scores:")
    print("-" * 70)
    for dim, row in s.items():
        print(f"  {dim:<14} {row['value']} [{row['confidence']:<6}]  "
              f"{row['rationale']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    conn = connect()
    cmd = sys.argv[1]
    if cmd == "summary":
        cmd_summary(conn)
    elif cmd == "gaps":
        cmd_gaps(conn)
    elif cmd in ("platform", "asset"):
        if len(sys.argv) < 3:
            print(f"Usage: score.py {cmd} <id>", file=sys.stderr)
            sys.exit(1)
        cmd_detail(conn, cmd, sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
