#!/usr/bin/env python3
"""
generate_outputs.py — Regenerate the three standard markdown outputs.

Reads the SQLite DB built by build_db.py and writes:
    outputs/platform_h2h.md    — platform × indication head-to-head matrix
    outputs/thesis_tracker.md  — asset-level thesis tracker
    outputs/deal_pulse.md      — rolling deal intelligence

Never hand-edit the output files. Regenerate from data.

Usage:
    python scripts/generate_outputs.py
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "lai.db"
OUT_DIR = REPO_ROOT / "outputs"

from score import (
    platform_scores, asset_scores, composite,
    PLATFORM_WEIGHTS, ASSET_WEIGHTS,
)

INDICATION_ORDER = [
    "psych", "addiction", "hiv", "oncology", "endocrine",
    "ophthalmology", "pain", "cns_neuro", "metabolic",
]


def connect():
    if not DB_PATH.exists():
        print(f"DB not found. Run: python scripts/build_db.py", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _score_cell(v: int | None, conf: str | None) -> str:
    """Format a score for the H2H matrix with a confidence marker."""
    if v is None:
        return "—"
    marker = {"high": "", "medium": "·", "low": "?"}.get(conf, "")
    return f"{v}{marker}"


def generate_platform_h2h(conn) -> str:
    platforms = list(conn.execute("SELECT id, name FROM platforms ORDER BY name"))
    # Collect which indications anyone scores
    indications_scored = set()
    for r in conn.execute("SELECT DISTINCT indication_code FROM indication_fit"):
        indications_scored.add(r["indication_code"])
    indications = [i for i in INDICATION_ORDER if i in indications_scored]

    # Build the matrix
    matrix = {p["id"]: {} for p in platforms}
    for r in conn.execute("SELECT platform_id, indication_code, value, confidence FROM indication_fit"):
        matrix[r["platform_id"]][r["indication_code"]] = (r["value"], r["confidence"])

    lines = [
        "# Platform Head-to-Head",
        "",
        f"*Generated {_today()} from `db/lai.db`. Do not hand-edit.*",
        "",
        "## Indication fit matrix",
        "",
        "Score 1 (fundamental mismatch) to 5 (best-in-class). Confidence markers: "
        "no marker = high; `·` = medium; `?` = low.",
        "",
    ]
    header = ["Platform"] + [i for i in indications]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for p in platforms:
        row = [p["name"]]
        for ind in indications:
            cell = matrix[p["id"]].get(ind, (None, None))
            row.append(_score_cell(*cell))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Platform composite scores")
    lines.append("")
    lines.append("| Platform | Tech | IP | Dealability | Composite |")
    lines.append("|---|---|---|---|---|")
    for p in platforms:
        s = platform_scores(conn, p["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, PLATFORM_WEIGHTS)
        comp_str = f"**{comp:.2f}**" if comp is not None else "—"
        lines.append(
            f"| {p['name']} | {vals.get('tech', '—')} | "
            f"{vals.get('ip', '—')} | {vals.get('dealability', '—')} | "
            f"{comp_str} |"
        )

    lines.append("")
    lines.append("## TactBio view per platform")
    lines.append("")
    for p in platforms:
        row = conn.execute("SELECT tactbio_view FROM platforms WHERE id=?", (p["id"],)).fetchone()
        lines.append(f"### {p['name']}")
        lines.append("")
        lines.append((row["tactbio_view"] or "_No TactBio view yet._").strip())
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_thesis_tracker(conn) -> str:
    assets = list(conn.execute("""
        SELECT a.id, a.name, a.inn, a.platform_id, a.owning_company,
               a.licensee_company, a.tactbio_view, a.indications_json,
               a.commercial_json, a.key_dates_json,
               p.name AS platform_name
        FROM assets a
        LEFT JOIN platforms p ON a.platform_id = p.id
        ORDER BY a.name
    """))

    lines = [
        "# Thesis Tracker",
        "",
        f"*Generated {_today()} from `db/lai.db`. Do not hand-edit.*",
        "",
        "## Summary table",
        "",
        "| Asset | INN | Platform | Owner / Licensee | Status | Composite | Next catalyst |",
        "|---|---|---|---|---|---|---|",
    ]

    for a in assets:
        indications = json.loads(a["indications_json"] or "[]")
        key_dates = json.loads(a["key_dates_json"] or "{}")
        status = indications[0].get("phase", "—") if indications else "—"
        owner = a["owning_company"] or "—"
        if a["licensee_company"]:
            owner += f" / {a['licensee_company']}"
        s = asset_scores(conn, a["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, ASSET_WEIGHTS)
        comp_str = f"**{comp:.2f}**" if comp is not None else "—"
        catalyst = key_dates.get("next_catalyst") or "—"
        lines.append(
            f"| {a['name']} | {a['inn'] or '—'} | {a['platform_name'] or '—'} | "
            f"{owner} | {status} | {comp_str} | {catalyst} |"
        )

    lines.append("")
    lines.append("## Asset detail")
    lines.append("")

    for a in assets:
        lines.append(f"### {a['name']} ({a['inn'] or ''})")
        lines.append("")
        lines.append(f"**Platform:** {a['platform_name']}  ")
        lines.append(f"**Owner:** {a['owning_company']}  ")
        if a["licensee_company"]:
            lines.append(f"**Licensee:** {a['licensee_company']}  ")
        commercial = json.loads(a["commercial_json"] or "{}")
        sales = commercial.get("sales_latest") or {}
        if sales.get("value_usd_m"):
            lines.append(
                f"**Sales {sales.get('year', '')}:** "
                f"${sales['value_usd_m']:.0f}M ({sales.get('source', 'company')})"
            )
        lines.append("")

        # Score table
        s = asset_scores(conn, a["id"])
        if s:
            lines.append("| Dimension | Score | Conf. | Rationale |")
            lines.append("|---|---|---|---|")
            for dim, row in s.items():
                lines.append(
                    f"| {dim} | {row['value']} | {row['confidence']} | "
                    f"{(row['rationale'] or '').replace('|', '\\|')} |"
                )
            lines.append("")

        if a["tactbio_view"]:
            lines.append("**TactBio view:** " + a["tactbio_view"].strip())
            lines.append("")

    return "\n".join(lines) + "\n"


def generate_deal_pulse(conn) -> str:
    deals = list(conn.execute("""
        SELECT d.*, p.name AS platform_name, a.name AS asset_name
        FROM deals d
        LEFT JOIN platforms p ON d.platform_id = p.id
        LEFT JOIN assets a ON d.asset_id = a.id
        ORDER BY d.announced_date DESC
    """))

    lines = [
        "# Deal Pulse",
        "",
        f"*Generated {_today()} from `db/lai.db`. "
        f"All-time deal log; filter by date for monthly publication.*",
        "",
        "## Deal log",
        "",
        "| Date | Licensor | Licensee | Platform | Type | Upfront | Milestones | Territory | Disclosure |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for d in deals:
        upfront = f"${d['upfront_usd_m']:.0f}M" if d["upfront_usd_m"] else "undisc."
        milestones = f"${d['milestones_total_usd_m']:.0f}M" if d["milestones_total_usd_m"] else "undisc."
        lines.append(
            f"| {d['announced_date']} | {d['licensor']} | {d['licensee']} | "
            f"{d['platform_name'] or '—'} | {d['deal_type']} | {upfront} | "
            f"{milestones} | {d['territory'] or '—'} | {d['disclosure_quality']} |"
        )

    lines.append("")
    lines.append("## Deal detail and TactBio view")
    lines.append("")
    for d in deals:
        lines.append(f"### {d['licensor']} × {d['licensee']} — {d['announced_date']}")
        lines.append("")
        lines.append(f"**Description:** {d['description']}  ")
        lines.append(f"**Type:** {d['deal_type']} | **Status:** {d['status']} | "
                     f"**Exclusivity:** {d['exclusivity']} | "
                     f"**Territory:** {d['territory']}  ")

        # Economics block
        econ = json.loads(d["economics_json"] or "{}")
        econ_lines = []
        if econ.get("upfront_usd_m"):
            econ_lines.append(f"Upfront ${econ['upfront_usd_m']:.0f}M")
        if econ.get("milestones_total_usd_m"):
            econ_lines.append(f"milestones ${econ['milestones_total_usd_m']:.0f}M")
        if econ.get("royalty_low_pct") or econ.get("royalty_high_pct"):
            lo, hi = econ.get("royalty_low_pct"), econ.get("royalty_high_pct")
            econ_lines.append(f"royalty {lo or '?'}%–{hi or '?'}%")
        if econ_lines:
            lines.append(f"**Economics:** {' · '.join(econ_lines)}  ")
        if econ.get("royalty_notes"):
            lines.append(f"*Notes:* {econ['royalty_notes'].strip()}")
        lines.append("")

        if d["tactbio_view"]:
            lines.append("**TactBio view:** " + d["tactbio_view"].strip())
            lines.append("")

    return "\n".join(lines) + "\n"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    print("Generating outputs...")

    outputs = {
        "platform_h2h.md": generate_platform_h2h(conn),
        "thesis_tracker.md": generate_thesis_tracker(conn),
        "deal_pulse.md": generate_deal_pulse(conn),
    }
    for name, content in outputs.items():
        path = OUT_DIR / name
        path.write_text(content)
        print(f"  wrote {path} ({len(content):,} chars)")

    print("Done.")


if __name__ == "__main__":
    main()
