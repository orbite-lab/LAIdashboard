#!/usr/bin/env python3
"""
generate_outputs.py — Regenerate the standard markdown outputs.

Reads the SQLite DB built by build_db.py and writes:
    outputs/platform_h2h.md      — platform × indication head-to-head + availability
    outputs/thesis_tracker.md    — asset-level thesis tracker (investor view)
    outputs/deal_pulse.md        — rolling deal intelligence
    outputs/partner_scout.md     — pharma BD scouting view
    outputs/target_screener.md   — M&A target screener

Never hand-edit the output files. Regenerate from data.

Usage:
    python scripts/generate_outputs.py
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict


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


def _score_cell(v: int | None, conf: str | None, encumbered: bool = False) -> str:
    """Format a score for the H2H matrix.

    `·` = medium confidence, `?` = low confidence; trailing `🔒` indicates
    the (platform, indication) is encumbered by an existing exclusive deal.
    """
    if v is None:
        return "—"
    marker = {"high": "", "medium": "·", "low": "?"}.get(conf, "")
    lock = " 🔒" if encumbered else ""
    return f"{v}{marker}{lock}"


def encumbrance_map(conn) -> dict[tuple[str, str], list[str]]:
    """{(platform_id, indication): [deal_ids]}"""
    out: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in conn.execute("SELECT platform_id, indication, deal_id FROM encumbrances"):
        if r["indication"]:
            out[(r["platform_id"], r["indication"])].append(r["deal_id"])
    return out


# -----------------------------------------------------------------------------
# Platform H2H
# -----------------------------------------------------------------------------

def generate_platform_h2h(conn) -> str:
    platforms = list(conn.execute("SELECT id, name FROM platforms ORDER BY name"))
    indications_scored = set()
    for r in conn.execute("SELECT DISTINCT indication_code FROM indication_fit"):
        indications_scored.add(r["indication_code"])
    indications = [i for i in INDICATION_ORDER if i in indications_scored]

    matrix = {p["id"]: {} for p in platforms}
    for r in conn.execute("SELECT platform_id, indication_code, value, confidence FROM indication_fit"):
        matrix[r["platform_id"]][r["indication_code"]] = (r["value"], r["confidence"])

    enc = encumbrance_map(conn)

    lines = [
        "# Platform Head-to-Head",
        "",
        f"*Generated {_today()} from `db/lai.db`. Do not hand-edit.*",
        "",
        "## Indication fit matrix",
        "",
        "Score 1 (fundamental mismatch) to 5 (best-in-class). Confidence markers: "
        "no marker = high; `·` = medium; `?` = low. `🔒` = indication encumbered "
        "by existing exclusive deal (see Partner Scout for details).",
        "",
    ]
    header = ["Platform"] + [i for i in indications]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for p in platforms:
        row = [p["name"]]
        for ind in indications:
            cell = matrix[p["id"]].get(ind, (None, None))
            encumbered = bool(enc.get((p["id"], ind)))
            row.append(_score_cell(*cell, encumbered=encumbered))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Platform composite scores")
    lines.append("")
    lines.append("Composite weights (v1): tech 0.30, ip 0.20, dealability 0.25, availability 0.25. "
                 "Platforms missing availability are scored on remaining weights renormalized.")
    lines.append("")
    lines.append("| Platform | Tech | IP | Dealability | Availability | Composite |")
    lines.append("|---|---|---|---|---|---|")
    for p in platforms:
        s = platform_scores(conn, p["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, PLATFORM_WEIGHTS)
        comp_str = f"**{comp:.2f}**" if comp is not None else "—"
        lines.append(
            f"| {p['name']} | {vals.get('tech', '—')} | "
            f"{vals.get('ip', '—')} | {vals.get('dealability', '—')} | "
            f"{vals.get('availability', '—')} | {comp_str} |"
        )

    lines.append("")
    lines.append("## TactBio view per platform (investor)")
    lines.append("")
    for p in platforms:
        row = conn.execute(
            "SELECT view_investor FROM platforms WHERE id=?", (p["id"],)
        ).fetchone()
        lines.append(f"### {p['name']}")
        lines.append("")
        lines.append((row["view_investor"] or "_No investor view yet._").strip())
        lines.append("")

    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# Thesis tracker
# -----------------------------------------------------------------------------

def generate_thesis_tracker(conn) -> str:
    assets = list(conn.execute("""
        SELECT a.id, a.name, a.inn, a.platform_id, a.owning_company,
               a.licensee_company, a.tactbio_view, a.view_investor,
               a.indications_json, a.commercial_json, a.key_dates_json,
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
        key_dates = json.loads(a["key_dates_json"] or "{}") or {}
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
        commercial = json.loads(a["commercial_json"] or "{}") or {}
        sales = (commercial.get("sales_latest") or {}) if commercial else {}
        if sales and sales.get("value_usd_m"):
            lines.append(
                f"**Sales {sales.get('year', '')}:** "
                f"${sales['value_usd_m']:.0f}M ({sales.get('source', 'company')})"
            )
        lines.append("")

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

        view = a["view_investor"] or a["tactbio_view"]
        if view:
            lines.append("**Investor view:** " + view.strip())
            lines.append("")

    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# Deal pulse
# -----------------------------------------------------------------------------

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

        econ = json.loads(d["economics_json"] or "{}") or {}
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


# -----------------------------------------------------------------------------
# Partner Scout (NEW v1)
# -----------------------------------------------------------------------------

def _fmt_range(lo, hi, unit=""):
    if lo is None and hi is None:
        return "—"
    return f"{lo or '?'}–{hi or '?'}{unit}"


def _fmt_payload(json_str: str) -> str:
    if not json_str:
        return "—"
    try:
        items = json.loads(json_str)
    except json.JSONDecodeError:
        return "—"
    if not items:
        return "—"
    return ", ".join(items)


def _fmt_indication_list(json_str: str) -> str:
    if not json_str:
        return "—"
    try:
        items = json.loads(json_str)
    except json.JSONDecodeError:
        return "—"
    if not items:
        return "(none)"
    return ", ".join(items)


def generate_partner_scout(conn) -> str:
    """Audience: pharma BD scouting LAI delivery solutions for their molecules."""
    platforms = list(conn.execute("""
        SELECT id, name, company, company_ticker, country, mechanism,
               duration_bucket, duration_min_days, duration_max_days,
               payload_classes_json, ip_core_expiry_year, open_to_partnering,
               open_indications_json, closed_indications_json,
               capacity_headroom, technical_fit_json, partnering_posture_json,
               view_partner, tactbio_view
        FROM platforms
        ORDER BY name
    """))

    enc = encumbrance_map(conn)

    lines = [
        "# Partner Scout",
        "",
        f"*Generated {_today()} from `db/lai.db`. For pharma BD use — identifies "
        "available LAI delivery platforms by indication, payload, duration, and "
        "encumbrance status.*",
        "",
        "## Availability by indication",
        "",
        "Each cell shows indication_fit score (1–5) and encumbrance status. "
        "`✓` = open for partnering on this indication. `🔒` = encumbered by an "
        "exclusive deal (see Encumbrance log below). `—` = no fit score.",
        "",
    ]

    indications_scored = set()
    for r in conn.execute("SELECT DISTINCT indication_code FROM indication_fit"):
        indications_scored.add(r["indication_code"])
    indications = [i for i in INDICATION_ORDER if i in indications_scored]

    fit = {}
    for r in conn.execute("SELECT platform_id, indication_code, value FROM indication_fit"):
        fit[(r["platform_id"], r["indication_code"])] = r["value"]

    header = ["Platform", "Posture"] + indications
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for p in platforms:
        row = [p["name"], (p["open_to_partnering"] or "—")]
        for ind in indications:
            v = fit.get((p["id"], ind))
            if v is None:
                row.append("—")
                continue
            encumbered = bool(enc.get((p["id"], ind)))
            mark = "🔒" if encumbered else "✓"
            row.append(f"{v} {mark}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    lines.append("## Platform technical fit")
    lines.append("")
    lines.append(
        "| Platform | Mechanism | Duration | Payloads | Inj. vol (mL) | Cold chain | Capacity |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for p in platforms:
        tf = json.loads(p["technical_fit_json"] or "{}") or {}
        vol = tf.get("injection_volume_ml_range") or [None, None]
        cold = tf.get("cold_chain_required")
        cold_str = "yes" if cold is True else "no" if cold is False else "—"
        duration = "—"
        if p["duration_min_days"] and p["duration_max_days"]:
            duration = f"{p['duration_min_days']}–{p['duration_max_days']}d"
        lines.append(
            f"| {p['name']} | {p['mechanism'] or '—'} | {duration} | "
            f"{_fmt_payload(p['payload_classes_json'])} | "
            f"{_fmt_range(vol[0], vol[1])} | {cold_str} | "
            f"{p['capacity_headroom'] or '—'} |"
        )

    lines.append("")
    lines.append("## Encumbrance log")
    lines.append("")
    lines.append(
        "Active exclusive deals locking up indication scope by platform. "
        "BD scouts should treat these scopes as unavailable absent termination."
    )
    lines.append("")
    encs = list(conn.execute("""
        SELECT e.platform_id, e.deal_id, e.indication, e.molecule_classes_json,
               e.compound_count_locked, e.territory, e.exclusivity, e.expires,
               p.name AS platform_name,
               d.licensee, d.announced_date
        FROM encumbrances e
        LEFT JOIN platforms p ON e.platform_id = p.id
        LEFT JOIN deals d ON e.deal_id = d.id
        ORDER BY p.name, e.indication
    """))
    if encs:
        lines.append(
            "| Platform | Indication | Locked by | Since | Molecules | Territory |"
        )
        lines.append("|---|---|---|---|---|---|")
        for e in encs:
            molecules = "—"
            if e["molecule_classes_json"]:
                try:
                    items = json.loads(e["molecule_classes_json"])
                    molecules = ", ".join(items) if items else "—"
                except json.JSONDecodeError:
                    pass
            lines.append(
                f"| {e['platform_name'] or e['platform_id']} | "
                f"{e['indication'] or '—'} | "
                f"{e['licensee'] or '—'} ({e['deal_id']}) | "
                f"{e['announced_date'] or '—'} | {molecules} | "
                f"{e['territory'] or '—'} |"
            )
    else:
        lines.append("_No encumbrances recorded._")

    lines.append("")
    lines.append("## Partner view per platform")
    lines.append("")
    for p in platforms:
        lines.append(f"### {p['name']} ({p['company'] or '—'})")
        lines.append("")
        # Open / closed quick read
        lines.append(
            f"**Posture:** {p['open_to_partnering'] or '—'}  "
        )
        lines.append(
            f"**Open indications:** {_fmt_indication_list(p['open_indications_json'])}  "
        )
        lines.append(
            f"**Closed indications:** {_fmt_indication_list(p['closed_indications_json'])}  "
        )
        lines.append("")
        view = p["view_partner"]
        if view and "Data pending" not in view:
            lines.append(view.strip())
            lines.append("")
        else:
            lines.append("_Partner view not yet populated for this platform._")
            lines.append("")

    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# Target Screener (NEW v1)
# -----------------------------------------------------------------------------

def generate_target_screener(conn) -> str:
    """Audience: pharma corp dev evaluating LAI biotech for M&A."""
    companies = list(conn.execute("""
        SELECT * FROM companies
        WHERE ticker IS NOT NULL AND ticker != ''
        ORDER BY market_cap_usd_m DESC NULLS LAST
    """))

    lines = [
        "# Target Screener",
        "",
        f"*Generated {_today()} from `db/lai.db`. For corp dev / M&A scouting — "
        "ranks LAI-platform-owning companies by enterprise scale, encumbrance, "
        "and pipeline depth.*",
        "",
        "## Public companies — at-a-glance",
        "",
        "| Company | Ticker | Listing | Mkt cap (USD M) | Cash (USD M) | Debt (USD M) | Platforms |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in companies:
        mc = f"{c['market_cap_usd_m']:.0f}" if c["market_cap_usd_m"] else "—"
        cash = f"{c['cash_position_usd_m']:.0f}" if c["cash_position_usd_m"] else "—"
        debt = f"{c['debt_usd_m']:.0f}" if c["debt_usd_m"] else "—"
        plats = "—"
        if c["related_platforms_json"]:
            try:
                items = json.loads(c["related_platforms_json"])
                plats = ", ".join(items) if items else "—"
            except json.JSONDecodeError:
                pass
        lines.append(
            f"| {c['name']} | {c['ticker'] or '—'} | {c['listing_venue'] or '—'} | "
            f"{mc} | {cash} | {debt} | {plats} |"
        )

    lines.append("")
    lines.append("## Acquirer view per company")
    lines.append("")
    for c in companies:
        lines.append(f"### {c['name']} ({c['ticker']})")
        lines.append("")
        lines.append(f"**HQ:** {c['country_hq'] or '—'}  ")
        lines.append(f"**Listing:** {c['listing_venue'] or '—'}  ")
        if c["market_cap_usd_m"]:
            lines.append(f"**Market cap:** ${c['market_cap_usd_m']:.0f}M (as of {c['market_cap_as_of'] or 'unknown'})  ")
        if c["cash_position_usd_m"]:
            lines.append(f"**Cash:** ${c['cash_position_usd_m']:.0f}M  ")
        if c["debt_usd_m"]:
            lines.append(f"**Debt:** ${c['debt_usd_m']:.0f}M  ")

        # M&A protections
        mna = json.loads(c["m_and_a_protections_json"] or "{}") or {}
        if mna:
            poison = mna.get("poison_pill")
            stagger = mna.get("staggered_board")
            if poison is not None or stagger is not None:
                lines.append(
                    f"**M&A protections:** poison pill = {poison}, staggered board = {stagger}  "
                )

        # Aggregate acquirer-views from related platforms
        related_platforms = []
        if c["related_platforms_json"]:
            try:
                related_platforms = json.loads(c["related_platforms_json"]) or []
            except json.JSONDecodeError:
                pass
        if related_platforms:
            lines.append("")
            lines.append("**Related platforms:**")
            for pid in related_platforms:
                row = conn.execute(
                    "SELECT name, view_acquirer FROM platforms WHERE id=?", (pid,)
                ).fetchone()
                if row and row["view_acquirer"] and "Data pending" not in row["view_acquirer"]:
                    lines.append(f"- **{row['name']}** — {row['view_acquirer'].strip()}")
                elif row:
                    lines.append(f"- **{row['name']}** _(acquirer view not yet populated)_")
        if c["notes"]:
            lines.append("")
            lines.append(c["notes"].strip())
        lines.append("")

    return "\n".join(lines) + "\n"


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    print("Generating outputs...")

    outputs = {
        "platform_h2h.md": generate_platform_h2h(conn),
        "thesis_tracker.md": generate_thesis_tracker(conn),
        "deal_pulse.md": generate_deal_pulse(conn),
        "partner_scout.md": generate_partner_scout(conn),
        "target_screener.md": generate_target_screener(conn),
    }
    for name, content in outputs.items():
        path = OUT_DIR / name
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path} ({len(content):,} chars)")

    print("Done.")


if __name__ == "__main__":
    main()
