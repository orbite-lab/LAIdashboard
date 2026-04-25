#!/usr/bin/env python3
"""
build_dashboard.py — Generate a self-contained HTML dashboard from the DB.

Produces outputs/dashboard.html — a single file with no external dependencies,
no JS, no CDN. Pure HTML + inline CSS. Opens offline in any browser. Emailable.

Design matches TactBio house style: navy header, blue/teal accents,
muted semantic colors for heatmap cells, low-confidence cells shown with
reduced opacity and a marker.

Usage:
    python scripts/build_dashboard.py
"""

import sys
import sqlite3
import json
import html
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "lai.db"
OUT_PATH = REPO_ROOT / "outputs" / "dashboard.html"

from score import (
    platform_scores, asset_scores, composite,
    PLATFORM_WEIGHTS, ASSET_WEIGHTS,
)

INDICATION_ORDER = [
    "psych", "addiction", "hiv", "oncology", "endocrine",
    "ophthalmology", "pain", "cns_neuro", "metabolic",
]
INDICATION_LABELS = {
    "psych": "Psych",
    "addiction": "Addiction",
    "hiv": "HIV",
    "oncology": "Oncology",
    "endocrine": "Endocrine",
    "ophthalmology": "Ophtho",
    "pain": "Pain",
    "cns_neuro": "CNS/Neuro",
    "metabolic": "Metabolic",
    "other": "Other",
}

# Heatmap colors — semantic, matching TactBio muted palette
SCORE_COLORS = {
    5: "#0E7C6B",   # deep teal
    4: "#5FA89A",   # muted teal
    3: "#C9B896",   # warm beige
    2: "#D89660",   # muted amber
    1: "#A84545",   # muted red
}
SCORE_TEXT_COLORS = {
    5: "#FFFFFF",
    4: "#FFFFFF",
    3: "#3D2E10",
    2: "#3D1C00",
    1: "#FFFFFF",
}
CONFIDENCE_OPACITY = {"high": 1.0, "medium": 0.78, "low": 0.52}
CONFIDENCE_MARKER = {"high": "", "medium": "·", "low": "?"}

# Brand palette
NAVY = "#0F1B2D"
ACCENT_BLUE = "#2E5090"
ACCENT_TEAL = "#0E7C6B"
PAPER = "#FAF8F3"
INK = "#1C1C1A"
MUTED = "#6B6B66"
BORDER = "#E0DCD0"


def esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def connect():
    if not DB_PATH.exists():
        print(f"DB not found. Run: python scripts/build_db.py", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────

def render_stats(conn) -> str:
    n_plat = conn.execute("SELECT COUNT(*) FROM platforms").fetchone()[0]
    n_asset = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    n_deal = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    approved = conn.execute(
        "SELECT COUNT(*) FROM assets WHERE indications_json LIKE '%approved%'"
    ).fetchone()[0]

    cards = [
        ("Platforms tracked", n_plat, ACCENT_BLUE),
        ("Assets tracked", n_asset, ACCENT_BLUE),
        ("Deals in log", n_deal, ACCENT_TEAL),
        ("Approved assets", approved, ACCENT_TEAL),
    ]
    items = ""
    for label, value, color in cards:
        items += f"""
        <div class="stat-card">
          <div class="stat-value" style="color:{color};">{value}</div>
          <div class="stat-label">{label}</div>
        </div>"""
    return f'<div class="stats-row">{items}</div>'


def render_h2h_matrix(conn) -> str:
    platforms = list(conn.execute("SELECT id, name FROM platforms ORDER BY name"))
    indications_scored = set(
        r["indication_code"] for r in conn.execute(
            "SELECT DISTINCT indication_code FROM indication_fit"
        )
    )
    indications = [i for i in INDICATION_ORDER if i in indications_scored]

    matrix = {p["id"]: {} for p in platforms}
    for r in conn.execute(
        "SELECT platform_id, indication_code, value, confidence, rationale FROM indication_fit"
    ):
        matrix[r["platform_id"]][r["indication_code"]] = dict(r)

    # Header row
    thead = '<th class="row-label">Platform</th>'
    for ind in indications:
        thead += f'<th class="col-label">{esc(INDICATION_LABELS.get(ind, ind))}</th>'
    # Body
    tbody = ""
    for p in platforms:
        tbody += f'<tr><td class="row-label">{esc(p["name"])}</td>'
        for ind in indications:
            cell = matrix[p["id"]].get(ind)
            if cell is None:
                tbody += '<td class="cell empty">—</td>'
            else:
                val = cell["value"]
                conf = cell["confidence"] or "medium"
                bg = SCORE_COLORS.get(val, "#CCC")
                fg = SCORE_TEXT_COLORS.get(val, INK)
                opacity = CONFIDENCE_OPACITY.get(conf, 1.0)
                marker = CONFIDENCE_MARKER.get(conf, "")
                tooltip = esc(f"{conf} confidence — {cell['rationale']}")
                tbody += (
                    f'<td class="cell" '
                    f'style="background:{bg};color:{fg};opacity:{opacity};" '
                    f'title="{tooltip}">'
                    f'{val}<span class="marker">{marker}</span>'
                    f'</td>'
                )
        tbody += '</tr>'

    legend = """
    <div class="legend">
      <span class="legend-item"><span class="sw" style="background:#0E7C6B;"></span>5 best-in-class</span>
      <span class="legend-item"><span class="sw" style="background:#5FA89A;"></span>4 above avg</span>
      <span class="legend-item"><span class="sw" style="background:#C9B896;"></span>3 neutral</span>
      <span class="legend-item"><span class="sw" style="background:#D89660;"></span>2 below avg</span>
      <span class="legend-item"><span class="sw" style="background:#A84545;"></span>1 weak</span>
      <span class="legend-item legend-conf">Confidence: full opacity = high; · medium; ? low</span>
    </div>"""

    return f"""
    <section class="card">
      <h2>Platform × Indication Fit</h2>
      <p class="subtitle">Hover any cell for the scoring rationale.</p>
      <div class="heatmap-wrap">
        <table class="heatmap">
          <thead><tr>{thead}</tr></thead>
          <tbody>{tbody}</tbody>
        </table>
      </div>
      {legend}
    </section>"""


def render_composite_bars(conn) -> str:
    platforms = list(conn.execute("SELECT id, name FROM platforms ORDER BY name"))
    rows = ""
    for p in platforms:
        s = platform_scores(conn, p["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, PLATFORM_WEIGHTS)
        if comp is None:
            continue
        pct = (comp / 5.0) * 100
        # Color the bar based on composite: ≥4 teal, 3-4 blue, <3 gray
        bar_color = ACCENT_TEAL if comp >= 4 else (ACCENT_BLUE if comp >= 3 else MUTED)
        segments = ""
        for dim, weight in PLATFORM_WEIGHTS.items():
            if dim in vals:
                seg_pct = (vals[dim] / 5.0) * weight * 100
                segments += (
                    f'<span class="seg" title="{esc(dim)}: {vals[dim]}/5" '
                    f'style="width:{seg_pct:.1f}%;background:{bar_color};"></span>'
                )
        rows += f"""
        <div class="bar-row">
          <div class="bar-label">{esc(p["name"])}</div>
          <div class="bar-track">{segments}</div>
          <div class="bar-value">{comp:.2f}</div>
        </div>"""

    return f"""
    <section class="card">
      <h2>Platform composite scores</h2>
      <p class="subtitle">Weighted: tech 40% · IP 30% · dealability 30%. Hover segments for dimension detail.</p>
      <div class="bars">{rows}</div>
    </section>"""


def render_asset_table(conn) -> str:
    assets = list(conn.execute("""
        SELECT a.id, a.name, a.inn, a.owning_company, a.licensee_company,
               a.indications_json, a.commercial_json, a.key_dates_json,
               p.name AS platform_name
        FROM assets a LEFT JOIN platforms p ON a.platform_id = p.id
        ORDER BY a.name
    """))

    rows = ""
    for a in assets:
        ind_list = json.loads(a["indications_json"] or "[]")
        status = ind_list[0].get("phase", "—") if ind_list else "—"
        indication = ind_list[0].get("code", "—") if ind_list else "—"
        commercial = json.loads(a["commercial_json"] or "{}")
        sales = commercial.get("sales_latest") or {}
        sales_str = "—"
        if sales.get("value_usd_m"):
            sales_str = f"${sales['value_usd_m']:.0f}M <span class='muted'>({sales.get('year','')})</span>"

        s = asset_scores(conn, a["id"])
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, ASSET_WEIGHTS)
        comp_str = f"<strong>{comp:.2f}</strong>" if comp is not None else "—"

        key_dates = json.loads(a["key_dates_json"] or "{}")
        catalyst = key_dates.get("next_catalyst") or "—"

        owner = esc(a["owning_company"])
        if a["licensee_company"]:
            owner += f" <span class='muted'>/ {esc(a['licensee_company'])}</span>"

        status_pill_color = {
            "approved": ACCENT_TEAL,
            "phase_3": ACCENT_BLUE,
            "phase_2": "#8B6F3E",
            "phase_1": MUTED,
            "preclinical": MUTED,
        }.get(status, MUTED)

        rows += f"""
        <tr>
          <td><strong>{esc(a["name"])}</strong><br/><span class="muted">{esc(a["inn"] or '')}</span></td>
          <td>{esc(a["platform_name"] or '—')}</td>
          <td>{owner}</td>
          <td>{esc(INDICATION_LABELS.get(indication, indication))}</td>
          <td><span class="pill" style="background:{status_pill_color}">{esc(status)}</span></td>
          <td>{sales_str}</td>
          <td>{catalyst}</td>
          <td style="text-align:right;">{comp_str}</td>
        </tr>"""

    return f"""
    <section class="card">
      <h2>Asset thesis tracker</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Asset</th><th>Platform</th><th>Owner</th>
            <th>Indication</th><th>Phase</th><th>Sales</th>
            <th>Next catalyst</th><th style="text-align:right;">Composite</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_deal_log(conn) -> str:
    deals = list(conn.execute("""
        SELECT d.*, p.name AS platform_name
        FROM deals d LEFT JOIN platforms p ON d.platform_id = p.id
        ORDER BY d.announced_date DESC
    """))
    if not deals:
        return ""
    rows = ""
    for d in deals:
        upfront = f"${d['upfront_usd_m']:.0f}M" if d["upfront_usd_m"] else "<span class='muted'>undisc.</span>"
        milestones = f"${d['milestones_total_usd_m']:.0f}M" if d["milestones_total_usd_m"] else "<span class='muted'>undisc.</span>"
        disc_color = {"full": ACCENT_TEAL, "partial": "#8B6F3E", "minimal": "#A84545"}.get(
            d["disclosure_quality"], MUTED
        )
        rows += f"""
        <tr>
          <td>{esc(d["announced_date"])}</td>
          <td><strong>{esc(d["licensor"])}</strong> × {esc(d["licensee"])}</td>
          <td>{esc(d["platform_name"] or '—')}</td>
          <td>{esc(d["deal_type"])}</td>
          <td>{upfront}</td>
          <td>{milestones}</td>
          <td>{esc(d["territory"] or '—')}</td>
          <td><span class="pill" style="background:{disc_color}">{esc(d["disclosure_quality"])}</span></td>
        </tr>"""
    return f"""
    <section class="card">
      <h2>Deal log</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Date</th><th>Counterparties</th><th>Platform</th>
            <th>Type</th><th>Upfront</th><th>Milestones</th>
            <th>Territory</th><th>Disclosure</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_gaps(conn) -> str:
    """Show which scores have low confidence — editorial discipline."""
    low_conf = list(conn.execute("""
        SELECT entity_type, entity_id, dimension, value, rationale
        FROM scores WHERE confidence='low'
        UNION ALL
        SELECT 'platform_indication', platform_id, indication_code, value, rationale
        FROM indication_fit WHERE confidence='low'
    """))
    if not low_conf:
        return ""
    rows = ""
    for r in low_conf:
        rows += f"""
        <li>
          <code>{esc(r['entity_type'])}:{esc(r['entity_id'])}.{esc(r['dimension'])}</code>
          scored <strong>{r['value']}</strong> —
          {esc(r['rationale'])}
        </li>"""
    return f"""
    <section class="card warning-card">
      <h2>Low-confidence scores — research queue</h2>
      <p class="subtitle">Every cell below needs validation before publication. Shown here so no low-confidence score makes it into a memo by accident.</p>
      <ul class="gap-list">{rows}</ul>
    </section>"""


# ─────────────────────────────────────────────────────────────────────
# Top-level
# ─────────────────────────────────────────────────────────────────────

CSS = f"""
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: {PAPER};
    color: {INK};
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }}
  header.page-header {{
    background: {NAVY};
    color: #FFFFFF;
    padding: 32px 40px;
    border-bottom: 4px solid {ACCENT_BLUE};
  }}
  header.page-header .brand {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    color: #7899C9;
    margin-bottom: 6px;
  }}
  header.page-header h1 {{
    font-size: 28px;
    font-weight: 400;
    letter-spacing: -0.3px;
  }}
  header.page-header .meta {{
    margin-top: 8px;
    font-size: 12px;
    color: #B0BEC5;
  }}
  main {{
    max-width: 1240px;
    margin: 0 auto;
    padding: 32px 40px 80px;
  }}
  .stats-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }}
  .stat-card {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 18px 20px;
  }}
  .stat-value {{
    font-size: 32px;
    font-weight: 300;
    line-height: 1;
  }}
  .stat-label {{
    margin-top: 4px;
    font-size: 11px;
    color: {MUTED};
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }}
  section.card {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 24px 28px;
    margin-bottom: 24px;
  }}
  section.card h2 {{
    font-size: 15px;
    font-weight: 600;
    color: {NAVY};
    text-transform: uppercase;
    letter-spacing: 1.2px;
    border-bottom: 1px solid {BORDER};
    padding-bottom: 10px;
    margin-bottom: 14px;
  }}
  .subtitle {{
    font-size: 12px;
    color: {MUTED};
    margin-bottom: 16px;
  }}

  /* Heatmap */
  .heatmap-wrap {{ overflow-x: auto; }}
  table.heatmap {{
    border-collapse: separate;
    border-spacing: 3px;
    font-size: 13px;
  }}
  table.heatmap th {{
    font-weight: 500;
    text-align: center;
    padding: 8px 12px;
    color: {MUTED};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }}
  table.heatmap th.row-label {{ text-align: left; }}
  table.heatmap td.row-label {{
    font-weight: 500;
    padding: 0 14px 0 4px;
    text-align: left;
    color: {INK};
  }}
  table.heatmap td.cell {{
    text-align: center;
    padding: 0;
    width: 68px;
    height: 44px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 16px;
    cursor: help;
    transition: transform 0.1s;
    vertical-align: middle;
  }}
  table.heatmap td.cell:hover {{ transform: scale(1.06); }}
  table.heatmap td.cell.empty {{ color: {MUTED}; font-weight: 300; }}
  table.heatmap .marker {{
    font-size: 10px;
    margin-left: 2px;
    vertical-align: super;
  }}
  .legend {{
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    font-size: 11px;
    color: {MUTED};
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend .sw {{
    width: 14px; height: 14px;
    border-radius: 3px;
    display: inline-block;
  }}
  .legend-conf {{ margin-left: auto; font-style: italic; }}

  /* Composite bars */
  .bar-row {{
    display: grid;
    grid-template-columns: 140px 1fr 60px;
    align-items: center;
    gap: 14px;
    padding: 8px 0;
  }}
  .bar-label {{ font-weight: 500; }}
  .bar-track {{
    height: 22px;
    background: #F3EFE6;
    border-radius: 3px;
    display: flex;
    overflow: hidden;
  }}
  .bar-track .seg {{
    display: block;
    height: 100%;
    border-right: 1px solid rgba(255,255,255,0.35);
    opacity: 0.92;
    transition: opacity 0.15s;
  }}
  .bar-track .seg:last-child {{ border-right: 0; }}
  .bar-track .seg:hover {{ opacity: 1; }}
  .bar-value {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: {NAVY};
  }}

  /* Data tables */
  table.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  table.data-table th {{
    background: #F7F4EC;
    text-align: left;
    padding: 10px 12px;
    font-weight: 600;
    color: {NAVY};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    border-bottom: 2px solid {BORDER};
  }}
  table.data-table td {{
    padding: 10px 12px;
    border-bottom: 1px solid {BORDER};
    vertical-align: top;
  }}
  table.data-table tr:last-child td {{ border-bottom: 0; }}
  .pill {{
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    color: #FFFFFF;
    padding: 2px 8px;
    border-radius: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .muted {{ color: {MUTED}; font-weight: 400; }}

  /* Gaps card */
  .warning-card {{
    border-left: 4px solid #D89660;
  }}
  .gap-list {{ list-style: none; font-size: 13px; }}
  .gap-list li {{
    padding: 8px 0;
    border-bottom: 1px dashed {BORDER};
  }}
  .gap-list li:last-child {{ border-bottom: 0; }}
  .gap-list code {{
    background: #F3EFE6;
    padding: 1px 6px;
    border-radius: 2px;
    font-size: 11px;
    color: {NAVY};
  }}

  footer {{
    text-align: center;
    padding: 24px;
    font-size: 11px;
    color: {MUTED};
  }}
  @media (max-width: 720px) {{
    .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
    .bar-row {{ grid-template-columns: 100px 1fr 50px; }}
    main {{ padding: 20px; }}
  }}
"""


def build_dashboard() -> str:
    conn = connect()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    body_sections = [
        render_stats(conn),
        render_h2h_matrix(conn),
        render_composite_bars(conn),
        render_asset_table(conn),
        render_deal_log(conn),
        render_gaps(conn),
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TactBio LAI Tracker — Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<header class="page-header">
  <div class="brand">TACTBIO RESEARCH</div>
  <h1>Long-Acting Injectable Tracker</h1>
  <div class="meta">Generated {generated} · Source of truth: <code>data/</code> YAML · Rebuild with <code>python scripts/build_dashboard.py</code></div>
</header>
<main>
{''.join(body_sections)}
</main>
<footer>
  TactBio Research · Internal use · Not investment advice · Regenerated each run from <code>db/lai.db</code>
</footer>
</body>
</html>
"""


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_str = build_dashboard()
    OUT_PATH.write_text(html_str)
    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"Wrote {OUT_PATH} ({size_kb} KB)")
    print(f"Open it with: open {OUT_PATH}")


if __name__ == "__main__":
    main()
