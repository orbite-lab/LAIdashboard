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
INDEX_PATH = REPO_ROOT / "index.html"

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
    n_trial = conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
    n_ip = conn.execute("SELECT COUNT(*) FROM ip_positions").fetchone()[0]
    n_company = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    approved = conn.execute(
        "SELECT COUNT(*) FROM assets WHERE indications_json LIKE '%approved%'"
    ).fetchone()[0]

    cards = [
        ("Platforms", n_plat, ACCENT_BLUE),
        ("Assets", n_asset, ACCENT_BLUE),
        ("Approved", approved, ACCENT_TEAL),
        ("Deals", n_deal, ACCENT_TEAL),
        ("Trials", n_trial, ACCENT_BLUE),
        ("IP records", n_ip, ACCENT_BLUE),
        ("Companies", n_company, ACCENT_TEAL),
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
        if not s:
            continue
        vals = {d: s[d]["value"] for d in s}
        comp = composite(vals, PLATFORM_WEIGHTS)
        if comp is None:
            continue
        # Color the bar based on composite: ≥4 teal, 3-4 blue, <3 gray
        bar_color = ACCENT_TEAL if comp >= 4 else (ACCENT_BLUE if comp >= 3 else MUTED)

        # Build segments with full rationale in title attribute (hover tooltip)
        segments = ""
        for dim, weight in PLATFORM_WEIGHTS.items():
            if dim not in vals:
                continue
            seg_pct = (vals[dim] / 5.0) * weight * 100
            score_row = s[dim]
            conf = score_row.get("confidence") or "medium"
            rationale = (score_row.get("rationale") or "").strip()
            # Tooltip: dimension, score, confidence, full rationale
            tip = f"{dim.upper()} {vals[dim]}/5 [{conf}] — {rationale}"
            segments += (
                f'<span class="seg" title="{esc(tip)}" '
                f'style="width:{seg_pct:.1f}%;background:{bar_color};"></span>'
            )

        # Build the click-to-expand details panel
        detail_rows = ""
        for dim in PLATFORM_WEIGHTS:
            if dim not in s:
                continue
            row = s[dim]
            conf = row.get("confidence") or "medium"
            rationale = esc((row.get("rationale") or "").strip())
            scorer = esc(row.get("scorer") or "")
            scored_at = esc(row.get("scored_at") or "")
            conf_badge = (
                f'<span class="conf-badge conf-{conf}">{conf}</span>'
            )
            detail_rows += f"""
            <tr>
              <td class="d-dim">{esc(dim)}</td>
              <td class="d-score">{row['value']}</td>
              <td class="d-conf">{conf_badge}</td>
              <td class="d-rat">{rationale}</td>
              <td class="d-meta">{scorer} · {scored_at}</td>
            </tr>"""

        # Pull tactbio_view (now neutral editorial commentary) for the panel
        view_row = conn.execute(
            "SELECT tactbio_view FROM platforms WHERE id=?", (p["id"],)
        ).fetchone()
        editorial = (view_row["tactbio_view"] or "").strip() if view_row else ""
        editorial_block = (
            f'<div class="d-editorial"><strong>Analytical view</strong><br>{esc(editorial)}</div>'
            if editorial else ""
        )

        rows += f"""
        <div class="bar-row" data-platform="{esc(p['id'])}" tabindex="0" role="button" aria-expanded="false">
          <div class="bar-label">{esc(p["name"])}</div>
          <div class="bar-track">{segments}</div>
          <div class="bar-value">{comp:.2f}</div>
          <div class="bar-toggle" aria-hidden="true">▸</div>
        </div>
        <div class="bar-detail" data-for="{esc(p['id'])}" hidden>
          <table class="d-table">
            <thead><tr><th>Dimension</th><th>Score</th><th>Confidence</th><th>Rationale</th><th>Scorer · Date</th></tr></thead>
            <tbody>{detail_rows}</tbody>
          </table>
          {editorial_block}
        </div>"""

    return f"""
    <section class="card">
      <h2>Platform composite scores</h2>
      <p class="subtitle">Weighted: tech 40% · IP 30% · dealability 30%. Hover any bar segment for the rationale; click a row to expand full detail.</p>
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
      <p class="subtitle">Click any column header to sort. Click again to reverse.</p>
      <table class="data-table sortable">
        <thead>
          <tr>
            <th data-sort="text">Asset</th>
            <th data-sort="text">Platform</th>
            <th data-sort="text">Owner</th>
            <th data-sort="text">Indication</th>
            <th data-sort="text">Phase</th>
            <th data-sort="number">Sales</th>
            <th data-sort="text">Next catalyst</th>
            <th data-sort="number" style="text-align:right;">Composite</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_deal_log(conn) -> str:
    deals = list(conn.execute("""
        SELECT d.*, p.name AS platform_name, a.name AS asset_name
        FROM deals d
        LEFT JOIN platforms p ON d.platform_id = p.id
        LEFT JOIN assets a ON d.asset_id = a.id
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
        # Build a short scope hint to disambiguate same-counterparty deals
        scope_hint = ""
        if d["asset_name"]:
            scope_hint = esc(d["asset_name"])
        else:
            # Infer from id when it includes a salient suffix (e.g. amendment, discontinuation)
            id_lower = d["id"].lower()
            if "amendment" in id_lower:
                scope_hint = "amendment"
            elif "discontinuation" in id_lower:
                scope_hint = "discontinuation"
            elif "olanzapine" in id_lower:
                scope_hint = "olanzapine LAI funding"
            elif "incretins" in id_lower:
                scope_hint = "cardiometabolic incretins"
            elif "signifor" in id_lower:
                scope_hint = "Signifor + osilodrostat"
            elif "iluvien" in id_lower:
                scope_hint = "Iluvien"
            elif "cabenuva" in id_lower:
                scope_hint = "Cabenuva"
            elif "bydureon" in id_lower:
                scope_hint = "Bydureon"
            elif "perseris" in id_lower:
                scope_hint = "Perseris"
            elif "camcevi" in id_lower:
                scope_hint = "Camcevi"
            elif "medincell" in id_lower:
                scope_hint = "BEPO (multi-program)"
        scope_html = (
            f"<br/><span class='muted' style='font-size:11px;'>{scope_hint}</span>"
            if scope_hint else ""
        )
        rows += f"""
        <tr>
          <td>{esc(d["announced_date"])}</td>
          <td><strong>{esc(d["licensor"])}</strong> × {esc(d["licensee"])}{scope_html}</td>
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
      <p class="subtitle">Click any column header to sort. Click again to reverse.</p>
      <table class="data-table sortable">
        <thead>
          <tr>
            <th data-sort="date">Date</th>
            <th data-sort="text">Counterparties</th>
            <th data-sort="text">Platform</th>
            <th data-sort="text">Type</th>
            <th data-sort="number">Upfront</th>
            <th data-sort="number">Milestones</th>
            <th data-sort="text">Territory</th>
            <th data-sort="text">Disclosure</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </section>"""


def render_partner_availability(conn) -> str:
    """Pharma BD view: indication x platform with encumbrance lock icons."""
    platforms = list(conn.execute(
        "SELECT id, name, open_to_partnering FROM platforms ORDER BY name"
    ))
    indications_scored = set(
        r["indication_code"] for r in conn.execute(
            "SELECT DISTINCT indication_code FROM indication_fit"
        )
    )
    indications = [i for i in INDICATION_ORDER if i in indications_scored]

    fit = {}
    for r in conn.execute(
        "SELECT platform_id, indication_code, value FROM indication_fit"
    ):
        fit[(r["platform_id"], r["indication_code"])] = r["value"]

    enc = {}
    for r in conn.execute(
        "SELECT DISTINCT platform_id, indication FROM encumbrances"
    ):
        if r["indication"]:
            enc.setdefault((r["platform_id"], r["indication"]), True)

    posture_color = {
        "selective": "#5FA89A",
        "true": "#0E7C6B",
        "false": "#A84545",
        "unknown": "#C9B896",
        "": "#C9B896",
    }

    thead = '<th class="row-label">Platform</th><th class="row-label">Posture</th>'
    for ind in indications:
        thead += f'<th class="col-label">{esc(INDICATION_LABELS.get(ind, ind))}</th>'

    tbody = ""
    for p in platforms:
        posture = (p["open_to_partnering"] or "unknown").lower()
        bg = posture_color.get(posture, "#C9B896")
        tbody += (
            f'<tr><td class="row-label">{esc(p["name"])}</td>'
            f'<td class="cell" style="background:{bg};color:#fff;">'
            f'{esc(posture)}</td>'
        )
        for ind in indications:
            v = fit.get((p["id"], ind))
            if v is None:
                tbody += '<td class="cell empty">—</td>'
                continue
            locked = enc.get((p["id"], ind), False)
            if locked:
                tbody += (
                    f'<td class="cell" style="background:#A84545;color:#fff;" '
                    f'title="Encumbered by exclusive deal">{v} 🔒</td>'
                )
            else:
                bg = SCORE_COLORS.get(v, "#CCC")
                fg = SCORE_TEXT_COLORS.get(v, INK)
                tbody += (
                    f'<td class="cell" style="background:{bg};color:{fg};" '
                    f'title="Open for partnering on this indication">{v} ✓</td>'
                )
        tbody += '</tr>'

    return f"""
    <section class="card">
      <h2>Partner Availability</h2>
      <p class="subtitle">For pharma BD scouting. ✓ = indication open for partnering.
        🔒 = encumbered by an active exclusive deal. Color follows the indication-fit score.</p>
      <div class="heatmap-wrap">
        <table class="heatmap">
          <thead><tr>{thead}</tr></thead>
          <tbody>{tbody}</tbody>
        </table>
      </div>
    </section>"""


def render_technical_fit(conn) -> str:
    """Side-by-side comparison of technical attributes for BD scientific diligence."""
    rows = list(conn.execute("""
        SELECT id, name, mechanism, duration_min_days, duration_max_days,
               payload_classes_json, technical_fit_json, capacity_headroom
        FROM platforms ORDER BY name
    """))

    body = ""
    for r in rows:
        tf = json.loads(r["technical_fit_json"] or "{}") or {}
        vol = tf.get("injection_volume_ml_range") or [None, None]
        vol_str = (
            f"{vol[0]}–{vol[1]}" if vol[0] is not None and vol[1] is not None
            else "—"
        )
        cold = tf.get("cold_chain_required")
        cold_str = "yes" if cold is True else ("no" if cold is False else "—")
        sites = tf.get("injection_site") or []
        sites_str = ", ".join(sites) if sites else "—"
        gauge = tf.get("needle_gauge_typical") or "—"
        try:
            payloads = ", ".join(json.loads(r["payload_classes_json"] or "[]"))
        except json.JSONDecodeError:
            payloads = "—"
        duration = (
            f"{r['duration_min_days']}–{r['duration_max_days']}d"
            if r["duration_min_days"] and r["duration_max_days"] else "—"
        )
        body += (
            f"<tr><td>{esc(r['name'])}</td>"
            f"<td>{esc(r['mechanism'])}</td>"
            f"<td>{duration}</td>"
            f"<td>{esc(payloads)}</td>"
            f"<td>{vol_str}</td>"
            f"<td>{esc(gauge)}</td>"
            f"<td>{cold_str}</td>"
            f"<td>{esc(sites_str)}</td>"
            f"<td>{esc(r['capacity_headroom'] or '—')}</td></tr>"
        )

    return f"""
    <section class="card">
      <h2>Platform Technical Fit</h2>
      <p class="subtitle">Label-derived screening attributes for pharma scientist BD diligence.</p>
      <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Platform</th><th>Mechanism</th><th>Duration</th>
          <th>Payloads</th><th>Vol (mL)</th><th>Needle</th>
          <th>Cold chain</th><th>Site</th><th>Capacity</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      </div>
    </section>"""


def render_encumbrance_log(conn) -> str:
    """Active exclusive deal scope locking up indication coverage."""
    rows = list(conn.execute("""
        SELECT e.platform_id, e.deal_id, e.indication, e.molecule_classes_json,
               e.territory, p.name AS platform_name,
               d.licensee, d.announced_date
        FROM encumbrances e
        LEFT JOIN platforms p ON e.platform_id = p.id
        LEFT JOIN deals d ON e.deal_id = d.id
        ORDER BY p.name, e.indication
    """))
    if not rows:
        return ""

    body = ""
    for r in rows:
        molecules = "—"
        if r["molecule_classes_json"]:
            try:
                items = json.loads(r["molecule_classes_json"])
                molecules = ", ".join(items) if items else "—"
            except json.JSONDecodeError:
                pass
        body += (
            f"<tr><td>{esc(r['platform_name'] or r['platform_id'])}</td>"
            f"<td>{esc(r['indication'] or '—')}</td>"
            f"<td>{esc(r['licensee'] or '—')}<br>"
            f"<small style='color:{MUTED};'>{esc(r['deal_id'])}</small></td>"
            f"<td>{esc(r['announced_date'] or '—')}</td>"
            f"<td>{esc(molecules)}</td>"
            f"<td>{esc(r['territory'] or '—')}</td></tr>"
        )

    return f"""
    <section class="card">
      <h2>Encumbrance Log</h2>
      <p class="subtitle">Active exclusive deals locking indication scope. BD scouts treat these as unavailable.</p>
      <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Platform</th><th>Indication</th><th>Locked by</th>
          <th>Since</th><th>Molecules</th><th>Territory</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      </div>
    </section>"""


def render_target_screener(conn) -> str:
    """Public companies sized for M&A scouting."""
    rows = list(conn.execute("""
        SELECT * FROM companies
        WHERE ticker IS NOT NULL AND ticker != ''
        ORDER BY market_cap_usd_m DESC
    """))

    body = ""
    for c in rows:
        plats = "—"
        if c["related_platforms_json"]:
            try:
                items = json.loads(c["related_platforms_json"])
                plats = ", ".join(items) if items else "—"
            except json.JSONDecodeError:
                pass
        mc = f"${c['market_cap_usd_m']:,.0f}M" if c["market_cap_usd_m"] else "—"
        cash = f"${c['cash_position_usd_m']:,.0f}M" if c["cash_position_usd_m"] else "—"
        debt = f"${c['debt_usd_m']:,.0f}M" if c["debt_usd_m"] else "—"
        body += (
            f"<tr><td>{esc(c['name'])}</td>"
            f"<td>{esc(c['ticker'])}</td>"
            f"<td>{esc(c['country_hq'])}</td>"
            f"<td style='text-align:right;'>{mc}</td>"
            f"<td style='text-align:right;'>{cash}</td>"
            f"<td style='text-align:right;'>{debt}</td>"
            f"<td>{esc(plats)}</td></tr>"
        )

    return f"""
    <section class="card">
      <h2>Target Screener</h2>
      <p class="subtitle">Public LAI-platform companies sized by market cap. M&A scouting view.</p>
      <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Company</th><th>Ticker</th><th>HQ</th>
          <th>Mkt cap</th><th>Cash</th><th>Debt</th><th>Platforms</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      </div>
    </section>"""


def render_trials_summary(conn) -> str:
    """Trial count and upcoming readouts by asset."""
    asset_counts = list(conn.execute("""
        SELECT a.id, a.name, p.name AS platform_name,
               COUNT(t.id) AS n_trials,
               SUM(CASE WHEN t.status IN ('enrolling','active','planning','readout-pending') THEN 1 ELSE 0 END) AS n_active,
               SUM(CASE WHEN t.phase=3 THEN 1 ELSE 0 END) AS n_phase3
        FROM assets a
        LEFT JOIN platforms p ON a.platform_id = p.id
        LEFT JOIN trials t ON t.asset_id = a.id
        GROUP BY a.id
        HAVING n_trials > 0
        ORDER BY n_trials DESC, a.name
    """))

    body = ""
    for r in asset_counts:
        body += (
            f"<tr><td>{esc(r['name'])}</td>"
            f"<td>{esc(r['platform_name'] or '—')}</td>"
            f"<td style='text-align:right;'>{r['n_trials']}</td>"
            f"<td style='text-align:right;'>{r['n_active'] or 0}</td>"
            f"<td style='text-align:right;'>{r['n_phase3'] or 0}</td></tr>"
        )

    n_total = conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
    n_phase3_total = conn.execute("SELECT COUNT(*) FROM trials WHERE phase=3").fetchone()[0]
    n_active_total = conn.execute(
        "SELECT COUNT(*) FROM trials WHERE status IN ('enrolling','active','planning','readout-pending')"
    ).fetchone()[0]

    return f"""
    <section class="card">
      <h2>Clinical Trials Coverage</h2>
      <p class="subtitle">{n_total} trials indexed; {n_active_total} active or pre-readout; {n_phase3_total} Phase 3.
        Sourced from ClinicalTrials.gov via <code>scripts/scrape_clinicaltrials.py</code>.</p>
      <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Asset</th><th>Platform</th>
          <th>Total trials</th><th>Active</th><th>Phase 3</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      </div>
    </section>"""


def render_ip_overview(conn) -> str:
    """IP record counts by platform with earliest expiry."""
    rows = list(conn.execute("""
        SELECT p.id, p.name,
               COUNT(ip.id) AS n_records,
               MIN(ip.expiry_date) AS earliest_expiry,
               MAX(ip.expiry_date) AS latest_expiry
        FROM platforms p
        LEFT JOIN ip_positions ip ON ip.platform_id = p.id
        GROUP BY p.id
        HAVING n_records > 0
        ORDER BY n_records DESC, p.name
    """))

    body = ""
    for r in rows:
        body += (
            f"<tr><td>{esc(r['name'])}</td>"
            f"<td style='text-align:right;'>{r['n_records']}</td>"
            f"<td>{esc(r['earliest_expiry'] or '—')}</td>"
            f"<td>{esc(r['latest_expiry'] or '—')}</td></tr>"
        )

    n_total = conn.execute("SELECT COUNT(*) FROM ip_positions").fetchone()[0]

    return f"""
    <section class="card">
      <h2>IP Coverage</h2>
      <p class="subtitle">{n_total} patent records indexed from FDA Orange Book and curated filings.
        Sourced via <code>scripts/scrape_orange_book.py</code>.</p>
      <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Platform</th><th>Patents</th>
          <th>Earliest expiry</th><th>Latest expiry</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      </div>
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
    grid-template-columns: 140px 1fr 60px 18px;
    align-items: center;
    gap: 14px;
    padding: 8px 6px;
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.12s;
  }}
  .bar-row:hover {{ background: #FAF6EC; }}
  .bar-row:focus {{ outline: 2px solid {ACCENT_BLUE}; outline-offset: -2px; }}
  .bar-row.is-open {{ background: #FAF6EC; }}
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
    cursor: help;
  }}
  .bar-track .seg:last-child {{ border-right: 0; }}
  .bar-track .seg:hover {{ opacity: 1; }}
  .bar-value {{
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    color: {NAVY};
  }}
  .bar-toggle {{
    color: {MUTED};
    font-size: 11px;
    text-align: center;
    transition: transform 0.18s;
  }}
  .bar-row.is-open .bar-toggle {{ transform: rotate(90deg); color: {ACCENT_BLUE}; }}

  /* Bar detail panel (click-to-expand) */
  .bar-detail {{
    padding: 6px 8px 18px 154px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 4px;
  }}
  .bar-detail[hidden] {{ display: none; }}
  table.d-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-bottom: 10px;
  }}
  table.d-table th {{
    text-align: left;
    padding: 6px 10px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: {MUTED};
    font-weight: 600;
    border-bottom: 1px solid {BORDER};
  }}
  table.d-table td {{
    padding: 8px 10px;
    border-bottom: 1px dashed {BORDER};
    vertical-align: top;
  }}
  table.d-table td.d-dim {{
    font-weight: 600;
    text-transform: capitalize;
    color: {NAVY};
    width: 90px;
  }}
  table.d-table td.d-score {{
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    width: 50px;
    color: {NAVY};
  }}
  table.d-table td.d-conf {{ width: 90px; }}
  table.d-table td.d-rat {{ color: {INK}; line-height: 1.55; }}
  table.d-table td.d-meta {{
    color: {MUTED};
    font-size: 11px;
    white-space: nowrap;
    width: 130px;
  }}
  .conf-badge {{
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 7px;
    border-radius: 9px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }}
  .conf-high   {{ background: #DDEFE8; color: #0F6E56; }}
  .conf-medium {{ background: #F2E5C6; color: #8B6F3E; }}
  .conf-low    {{ background: #F2D6D2; color: #A84545; }}
  .d-editorial {{
    background: #F7F4EC;
    border-left: 3px solid {ACCENT_BLUE};
    padding: 10px 14px;
    border-radius: 3px;
    font-size: 12.5px;
    line-height: 1.6;
    color: {INK};
  }}
  .d-editorial strong {{
    color: {NAVY};
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    display: block;
    margin-bottom: 4px;
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
  table.data-table.sortable th {{
    cursor: pointer;
    user-select: none;
    padding-right: 22px;
    position: relative;
    transition: background 0.12s;
  }}
  table.data-table.sortable th:hover {{
    background: #EFE9DA;
  }}
  table.data-table.sortable th::after {{
    content: '↕';
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    color: {MUTED};
    font-size: 9px;
    opacity: 0.5;
  }}
  table.data-table.sortable th.sort-asc::after {{
    content: '↑';
    color: {ACCENT_BLUE};
    opacity: 1;
  }}
  table.data-table.sortable th.sort-desc::after {{
    content: '↓';
    color: {ACCENT_BLUE};
    opacity: 1;
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
    .bar-row {{ grid-template-columns: 100px 1fr 50px 16px; }}
    .bar-detail {{ padding-left: 12px; }}
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
        render_partner_availability(conn),
        render_technical_fit(conn),
        render_encumbrance_log(conn),
        render_asset_table(conn),
        render_target_screener(conn),
        render_deal_log(conn),
        render_trials_summary(conn),
        render_ip_overview(conn),
        render_gaps(conn),
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Long-Acting Injectable Tracker — Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<header class="page-header">
  <div class="brand">LAI RESEARCH</div>
  <h1>Long-Acting Injectable Tracker</h1>
  <div class="meta">Generated {generated}</div>
</header>
<main>
{''.join(body_sections)}
</main>
<footer>
  Internal use · Not investment advice
</footer>
<script>
(function() {{
  var EMPTY_MARKERS = ['—', '-', 'undisc.', 'undisclosed', '', 'null', 'n/a'];

  function parseNumber(text) {{
    if (!text) return null;
    var t = text.replace(/<[^>]+>/g, '').trim();
    if (EMPTY_MARKERS.indexOf(t.toLowerCase()) !== -1) return null;
    var m = t.match(/-?[\\d,]+\\.?\\d*/);
    if (!m) return null;
    var n = parseFloat(m[0].replace(/,/g, ''));
    return isNaN(n) ? null : n;
  }}

  function parseDate(text) {{
    if (!text) return null;
    var t = text.replace(/<[^>]+>/g, '').trim();
    if (EMPTY_MARKERS.indexOf(t.toLowerCase()) !== -1) return null;
    var d = new Date(t);
    return isNaN(d.getTime()) ? null : d.getTime();
  }}

  function getCellValue(row, idx, type) {{
    var cell = row.children[idx];
    if (!cell) return null;
    var raw = cell.textContent.trim();
    if (type === 'number') return parseNumber(raw);
    if (type === 'date')   return parseDate(raw);
    return raw.toLowerCase();
  }}

  function compareValues(a, b, dir) {{
    var aNull = (a === null || a === undefined || a === '');
    var bNull = (b === null || b === undefined || b === '');
    if (aNull && bNull) return 0;
    if (aNull) return 1;   // empties always at bottom
    if (bNull) return -1;
    if (a < b) return dir === 'asc' ? -1 : 1;
    if (a > b) return dir === 'asc' ? 1 : -1;
    return 0;
  }}

  function sortTable(table, colIdx, type, dir) {{
    var tbody = table.querySelector('tbody');
    var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    rows.sort(function(r1, r2) {{
      return compareValues(
        getCellValue(r1, colIdx, type),
        getCellValue(r2, colIdx, type),
        dir
      );
    }});
    rows.forEach(function(r) {{ tbody.appendChild(r); }});
  }}

  document.querySelectorAll('table.data-table.sortable').forEach(function(table) {{
    var headers = table.querySelectorAll('thead th');
    headers.forEach(function(th, idx) {{
      th.addEventListener('click', function() {{
        var type = th.getAttribute('data-sort') || 'text';
        var current = th.classList.contains('sort-asc') ? 'asc'
                    : th.classList.contains('sort-desc') ? 'desc' : null;
        var nextDir = current === 'asc' ? 'desc' : 'asc';
        headers.forEach(function(h) {{ h.classList.remove('sort-asc', 'sort-desc'); }});
        th.classList.add(nextDir === 'asc' ? 'sort-asc' : 'sort-desc');
        sortTable(table, idx, type, nextDir);
      }});
    }});
  }});

  // Bar-row click-to-expand for platform composite scores
  function toggleBarRow(row) {{
    var pid = row.getAttribute('data-platform');
    if (!pid) return;
    var detail = document.querySelector('.bar-detail[data-for="' + pid + '"]');
    if (!detail) return;
    var isOpen = !detail.hasAttribute('hidden');
    if (isOpen) {{
      detail.setAttribute('hidden', '');
      row.classList.remove('is-open');
      row.setAttribute('aria-expanded', 'false');
    }} else {{
      detail.removeAttribute('hidden');
      row.classList.add('is-open');
      row.setAttribute('aria-expanded', 'true');
    }}
  }}

  document.querySelectorAll('.bar-row[data-platform]').forEach(function(row) {{
    row.addEventListener('click', function(e) {{
      // Don't toggle if user is hovering a segment for tooltip — segments
      // intercept their own clicks too, so check the actual target
      if (e.target.classList.contains('seg')) {{ return; }}
      toggleBarRow(row);
    }});
    row.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter' || e.key === ' ') {{
        e.preventDefault();
        toggleBarRow(row);
      }}
    }});
  }});
}})();
</script>
</body>
</html>
"""


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html_str = build_dashboard()
    OUT_PATH.write_text(html_str, encoding="utf-8")
    INDEX_PATH.write_text(html_str, encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size // 1024
    print(f"Wrote {OUT_PATH} ({size_kb} KB)")
    print(f"Wrote {INDEX_PATH} ({size_kb} KB) — for GitHub Pages root")
    print(f"Open it with: open {OUT_PATH}")


if __name__ == "__main__":
    main()
