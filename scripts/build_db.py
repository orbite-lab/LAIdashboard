#!/usr/bin/env python3
"""
build_db.py — Compile YAML data files into SQLite.

Reads all files in data/{platforms,assets,deals,trials,ip,companies}/*.yaml
and writes db/lai.db. The SQLite DB is a derived artifact — never edit it
directly.

Usage:
    python scripts/build_db.py
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = REPO_ROOT / "db" / "lai.db"

SCHEMA = """
DROP TABLE IF EXISTS platforms;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS deals;
DROP TABLE IF EXISTS trials;
DROP TABLE IF EXISTS ip_positions;
DROP TABLE IF EXISTS companies;
DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS indication_fit;
DROP TABLE IF EXISTS scores_history;
DROP TABLE IF EXISTS encumbrances;

CREATE TABLE platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT,
    company_id TEXT,
    company_ticker TEXT,
    country TEXT,
    mechanism TEXT,
    duration_bucket TEXT,
    duration_min_days INTEGER,
    duration_max_days INTEGER,
    payload_classes_json TEXT,
    mechanism_notes TEXT,
    regulatory_history_json TEXT,
    ip_core_expiry_year INTEGER,
    ip_continuation_strategy TEXT,
    ip_fto_concerns TEXT,
    ip_notes TEXT,
    ip_records_json TEXT,
    active_partners_json TEXT,
    partnering_posture_json TEXT,
    open_to_partnering TEXT,
    open_indications_json TEXT,
    closed_indications_json TEXT,
    technical_fit_json TEXT,
    cmc_capacity_json TEXT,
    capacity_headroom TEXT,
    tactbio_view TEXT,
    view_investor TEXT,
    view_partner TEXT,
    view_acquirer TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    inn TEXT,
    platform_id TEXT,
    owning_company TEXT,
    licensee_company TEXT,
    indications_json TEXT,
    key_dates_json TEXT,
    commercial_json TEXT,
    primary_deal_id TEXT,
    primary_trials_json TEXT,
    tactbio_view TEXT,
    view_investor TEXT,
    view_partner TEXT,
    view_acquirer TEXT,
    last_updated TEXT,
    raw_json TEXT,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

CREATE TABLE deals (
    id TEXT PRIMARY KEY,
    deal_type TEXT,
    status TEXT,
    licensor TEXT,
    licensor_ticker TEXT,
    licensee TEXT,
    licensee_ticker TEXT,
    asset_id TEXT,
    platform_id TEXT,
    description TEXT,
    announced_date TEXT,
    completed_date TEXT,
    termination_date TEXT,
    upfront_usd_m REAL,
    milestones_total_usd_m REAL,
    royalty_low_pct REAL,
    royalty_high_pct REAL,
    economics_json TEXT,
    option_structure TEXT,
    territory TEXT,
    exclusivity TEXT,
    indications_covered_json TEXT,
    termination_clauses TEXT,
    disclosure_quality TEXT,
    source_urls_json TEXT,
    tactbio_view TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE trials (
    id TEXT PRIMARY KEY,
    nct_id TEXT,
    asset_id TEXT,
    indication TEXT,
    phase INTEGER,
    n INTEGER,
    design TEXT,
    primary_endpoint TEXT,
    control_arm TEXT,
    sponsor TEXT,
    status TEXT,
    start_date TEXT,
    expected_readout TEXT,
    result TEXT,
    geography_json TEXT,
    source_urls_json TEXT,
    notes TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE ip_positions (
    id TEXT PRIMARY KEY,
    patent_number TEXT,
    jurisdiction TEXT,
    assignee TEXT,
    platform_id TEXT,
    asset_id TEXT,
    filing_date TEXT,
    priority_date TEXT,
    grant_date TEXT,
    expiry_date TEXT,
    claim_type TEXT,
    continuation_lineage_json TEXT,
    paragraph_iv_filers_json TEXT,
    ipr_petitions_json TEXT,
    opposition_history TEXT,
    notes TEXT,
    source_urls_json TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ticker TEXT,
    listing_venue TEXT,
    country_hq TEXT,
    employees TEXT,
    market_cap_usd_m REAL,
    market_cap_as_of TEXT,
    cash_position_usd_m REAL,
    cash_runway_quarters REAL,
    debt_usd_m REAL,
    ifrs_or_gaap TEXT,
    governance_notes TEXT,
    m_and_a_protections_json TEXT,
    related_platforms_json TEXT,
    related_assets_json TEXT,
    related_deals_json TEXT,
    ir_contact TEXT,
    notes TEXT,
    last_updated TEXT,
    raw_json TEXT
);

CREATE TABLE scores (
    entity_type TEXT,
    entity_id TEXT,
    dimension TEXT,
    value INTEGER,
    rationale TEXT,
    confidence TEXT,
    scored_at TEXT,
    scorer TEXT,
    inherited_from TEXT,
    PRIMARY KEY (entity_type, entity_id, dimension)
);

CREATE TABLE indication_fit (
    platform_id TEXT,
    indication_code TEXT,
    value INTEGER,
    rationale TEXT,
    confidence TEXT,
    scored_at TEXT,
    scorer TEXT,
    PRIMARY KEY (platform_id, indication_code),
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

CREATE TABLE scores_history (
    entity_type TEXT,
    entity_id TEXT,
    dimension TEXT,
    value INTEGER,
    rationale TEXT,
    confidence TEXT,
    scored_at TEXT,
    scorer TEXT,
    recorded_at TEXT
);

CREATE TABLE encumbrances (
    platform_id TEXT,
    deal_id TEXT,
    indication TEXT,
    molecule_classes_json TEXT,
    compound_count_locked INTEGER,
    territory TEXT,
    exclusivity TEXT,
    expires TEXT,
    FOREIGN KEY (platform_id) REFERENCES platforms(id),
    FOREIGN KEY (deal_id) REFERENCES deals(id)
);

CREATE INDEX idx_assets_platform ON assets(platform_id);
CREATE INDEX idx_deals_platform ON deals(platform_id);
CREATE INDEX idx_deals_asset ON deals(asset_id);
CREATE INDEX idx_deals_announced ON deals(announced_date);
CREATE INDEX idx_scores_entity ON scores(entity_type, entity_id);
CREATE INDEX idx_indication_fit_platform ON indication_fit(platform_id);
CREATE INDEX idx_trials_asset ON trials(asset_id);
CREATE INDEX idx_ip_platform ON ip_positions(platform_id);
CREATE INDEX idx_ip_asset ON ip_positions(asset_id);
CREATE INDEX idx_encumbrances_platform ON encumbrances(platform_id);
CREATE INDEX idx_encumbrances_indication ON encumbrances(indication);
"""


def load_yaml_dir(path: Path) -> list[dict]:
    entries = []
    if not path.exists():
        return entries
    for f in sorted(path.glob("*.yaml")):
        with open(f, encoding="utf-8") as fh:
            try:
                data = yaml.safe_load(fh)
                if data is None:
                    print(f"  SKIP (empty): {f.name}")
                    continue
                data["_source_file"] = f.name
                entries.append(data)
            except yaml.YAMLError as e:
                print(f"  ERROR parsing {f}: {e}", file=sys.stderr)
                sys.exit(1)
    return entries


def _j(obj) -> str:
    """Serialize to JSON, handling None and date/datetime via str fallback."""
    return json.dumps(obj, default=str) if obj is not None else None


def _view(p: dict, audience: str) -> str | None:
    """Pull views.<audience> if present, fall back to legacy tactbio_view for investor."""
    views = p.get("views") or {}
    v = views.get(audience)
    if v:
        return v
    if audience == "investor":
        return p.get("tactbio_view")
    return None


def insert_platform(cur, p: dict):
    dr = p.get("duration_range_days") or [None, None]
    posture = p.get("partnering_posture") or {}
    tech_fit = p.get("technical_fit") or {}
    cmc = p.get("cmc_capacity") or {}
    cur.execute("""
        INSERT INTO platforms VALUES (
            :id, :name, :company, :company_id, :company_ticker, :country,
            :mechanism, :duration_bucket, :duration_min_days, :duration_max_days,
            :payload_classes_json, :mechanism_notes, :regulatory_history_json,
            :ip_core_expiry_year, :ip_continuation_strategy, :ip_fto_concerns, :ip_notes,
            :ip_records_json, :active_partners_json,
            :partnering_posture_json, :open_to_partnering,
            :open_indications_json, :closed_indications_json,
            :technical_fit_json, :cmc_capacity_json, :capacity_headroom,
            :tactbio_view, :view_investor, :view_partner, :view_acquirer,
            :last_updated, :raw_json
        )
    """, {
        "id": p["id"],
        "name": p["name"],
        "company": p.get("company"),
        "company_id": p.get("company_id"),
        "company_ticker": p.get("company_ticker"),
        "country": p.get("country"),
        "mechanism": p.get("mechanism"),
        "duration_bucket": p.get("duration_bucket"),
        "duration_min_days": dr[0],
        "duration_max_days": dr[1],
        "payload_classes_json": _j(p.get("payload_classes")),
        "mechanism_notes": p.get("mechanism_notes"),
        "regulatory_history_json": _j(p.get("regulatory_history")),
        "ip_core_expiry_year": p.get("ip_core_expiry_year"),
        "ip_continuation_strategy": p.get("ip_continuation_strategy"),
        "ip_fto_concerns": p.get("ip_fto_concerns"),
        "ip_notes": p.get("ip_notes"),
        "ip_records_json": _j(p.get("ip_records")),
        "active_partners_json": _j(p.get("active_partners")),
        "partnering_posture_json": _j(posture),
        "open_to_partnering": str(posture.get("open_to_partnering") or ""),
        "open_indications_json": _j(posture.get("open_indications")),
        "closed_indications_json": _j(posture.get("closed_indications")),
        "technical_fit_json": _j(tech_fit),
        "cmc_capacity_json": _j(cmc),
        "capacity_headroom": cmc.get("capacity_headroom"),
        "tactbio_view": p.get("tactbio_view"),
        "view_investor": _view(p, "investor"),
        "view_partner": _view(p, "partner"),
        "view_acquirer": _view(p, "acquirer"),
        "last_updated": str(p.get("last_updated", "")),
        "raw_json": json.dumps(p, default=str),
    })
    # Scores
    for dim, s in (p.get("scores") or {}).items():
        insert_score(cur, "platform", p["id"], dim, s)
    # Indication fit
    for ind, s in (p.get("indication_fit") or {}).items():
        cur.execute("""
            INSERT INTO indication_fit VALUES (
                :platform_id, :indication_code, :value, :rationale,
                :confidence, :scored_at, :scorer
            )
        """, {
            "platform_id": p["id"],
            "indication_code": ind,
            "value": s["value"],
            "rationale": s.get("rationale"),
            "confidence": s.get("confidence"),
            "scored_at": str(s.get("scored_at", "")),
            "scorer": s.get("scorer"),
        })
    # Encumbrances — explode each indication into its own row for filterability
    for enc in p.get("encumbrances") or []:
        for ind in enc.get("indications") or [None]:
            cur.execute("""
                INSERT INTO encumbrances VALUES (
                    :platform_id, :deal_id, :indication, :molecule_classes_json,
                    :compound_count_locked, :territory, :exclusivity, :expires
                )
            """, {
                "platform_id": p["id"],
                "deal_id": enc.get("deal_id"),
                "indication": ind,
                "molecule_classes_json": _j(enc.get("molecule_classes")),
                "compound_count_locked": enc.get("compound_count_locked"),
                "territory": enc.get("territory"),
                "exclusivity": enc.get("exclusivity"),
                "expires": str(enc.get("expires") or ""),
            })


def insert_asset(cur, a: dict):
    cur.execute("""
        INSERT INTO assets VALUES (
            :id, :name, :inn, :platform_id, :owning_company, :licensee_company,
            :indications_json, :key_dates_json, :commercial_json,
            :primary_deal_id, :primary_trials_json, :tactbio_view,
            :view_investor, :view_partner, :view_acquirer,
            :last_updated, :raw_json
        )
    """, {
        "id": a["id"],
        "name": a["name"],
        "inn": a.get("inn"),
        "platform_id": a.get("platform_id"),
        "owning_company": a.get("owning_company"),
        "licensee_company": a.get("licensee_company"),
        "indications_json": _j(a.get("indications")),
        "key_dates_json": _j(a.get("key_dates")),
        "commercial_json": _j(a.get("commercial")),
        "primary_deal_id": a.get("primary_deal_id"),
        "primary_trials_json": _j(a.get("primary_trials")),
        "tactbio_view": a.get("tactbio_view"),
        "view_investor": _view(a, "investor"),
        "view_partner": _view(a, "partner"),
        "view_acquirer": _view(a, "acquirer"),
        "last_updated": str(a.get("last_updated", "")),
        "raw_json": json.dumps(a, default=str),
    })
    for dim, s in (a.get("scores") or {}).items():
        insert_score(cur, "asset", a["id"], dim, s)


def insert_deal(cur, d: dict):
    econ = d.get("economics") or {}
    cur.execute("""
        INSERT INTO deals VALUES (
            :id, :deal_type, :status, :licensor, :licensor_ticker,
            :licensee, :licensee_ticker, :asset_id, :platform_id,
            :description, :announced_date, :completed_date, :termination_date,
            :upfront_usd_m, :milestones_total_usd_m, :royalty_low_pct, :royalty_high_pct,
            :economics_json, :option_structure, :territory, :exclusivity,
            :indications_covered_json, :termination_clauses, :disclosure_quality,
            :source_urls_json, :tactbio_view, :last_updated, :raw_json
        )
    """, {
        "id": d["id"],
        "deal_type": d.get("deal_type"),
        "status": d.get("status"),
        "licensor": d.get("licensor"),
        "licensor_ticker": d.get("licensor_ticker"),
        "licensee": d.get("licensee"),
        "licensee_ticker": d.get("licensee_ticker"),
        "asset_id": d.get("asset_id"),
        "platform_id": d.get("platform_id"),
        "description": d.get("description"),
        "announced_date": str(d.get("announced_date", "")),
        "completed_date": str(d.get("completed_date", "")),
        "termination_date": str(d.get("termination_date", "")) if d.get("termination_date") else None,
        "upfront_usd_m": econ.get("upfront_usd_m"),
        "milestones_total_usd_m": econ.get("milestones_total_usd_m"),
        "royalty_low_pct": econ.get("royalty_low_pct"),
        "royalty_high_pct": econ.get("royalty_high_pct"),
        "economics_json": _j(econ),
        "option_structure": d.get("option_structure"),
        "territory": d.get("territory"),
        "exclusivity": d.get("exclusivity"),
        "indications_covered_json": _j(d.get("indications_covered")),
        "termination_clauses": d.get("termination_clauses"),
        "disclosure_quality": d.get("disclosure_quality"),
        "source_urls_json": _j(d.get("source_urls")),
        "tactbio_view": d.get("tactbio_view"),
        "last_updated": str(d.get("last_updated", "")),
        "raw_json": json.dumps(d, default=str),
    })


def insert_trial(cur, t: dict):
    cur.execute("""
        INSERT INTO trials VALUES (
            :id, :nct_id, :asset_id, :indication, :phase, :n,
            :design, :primary_endpoint, :control_arm, :sponsor, :status,
            :start_date, :expected_readout, :result,
            :geography_json, :source_urls_json, :notes, :last_updated, :raw_json
        )
    """, {
        "id": t["id"],
        "nct_id": t.get("nct_id"),
        "asset_id": t.get("asset_id"),
        "indication": t.get("indication"),
        "phase": t.get("phase"),
        "n": t.get("n"),
        "design": t.get("design"),
        "primary_endpoint": t.get("primary_endpoint"),
        "control_arm": t.get("control_arm"),
        "sponsor": t.get("sponsor"),
        "status": t.get("status"),
        "start_date": str(t.get("start_date") or ""),
        "expected_readout": str(t.get("expected_readout") or ""),
        "result": t.get("result"),
        "geography_json": _j(t.get("geography")),
        "source_urls_json": _j(t.get("source_urls")),
        "notes": t.get("notes"),
        "last_updated": str(t.get("last_updated", "")),
        "raw_json": json.dumps(t, default=str),
    })


def insert_ip(cur, ip: dict):
    cur.execute("""
        INSERT INTO ip_positions VALUES (
            :id, :patent_number, :jurisdiction, :assignee, :platform_id, :asset_id,
            :filing_date, :priority_date, :grant_date, :expiry_date, :claim_type,
            :continuation_lineage_json, :paragraph_iv_filers_json, :ipr_petitions_json,
            :opposition_history, :notes, :source_urls_json, :last_updated, :raw_json
        )
    """, {
        "id": ip["id"],
        "patent_number": ip.get("patent_number"),
        "jurisdiction": ip.get("jurisdiction"),
        "assignee": ip.get("assignee"),
        "platform_id": ip.get("platform_id"),
        "asset_id": ip.get("asset_id"),
        "filing_date": str(ip.get("filing_date") or ""),
        "priority_date": str(ip.get("priority_date") or ""),
        "grant_date": str(ip.get("grant_date") or ""),
        "expiry_date": str(ip.get("expiry_date") or ""),
        "claim_type": ip.get("claim_type"),
        "continuation_lineage_json": _j(ip.get("continuation_lineage")),
        "paragraph_iv_filers_json": _j(ip.get("paragraph_iv_filers")),
        "ipr_petitions_json": _j(ip.get("ipr_petitions")),
        "opposition_history": ip.get("opposition_history"),
        "notes": ip.get("notes"),
        "source_urls_json": _j(ip.get("source_urls")),
        "last_updated": str(ip.get("last_updated", "")),
        "raw_json": json.dumps(ip, default=str),
    })


def insert_company(cur, c: dict):
    cur.execute("""
        INSERT INTO companies VALUES (
            :id, :name, :ticker, :listing_venue, :country_hq, :employees,
            :market_cap_usd_m, :market_cap_as_of,
            :cash_position_usd_m, :cash_runway_quarters, :debt_usd_m,
            :ifrs_or_gaap, :governance_notes, :m_and_a_protections_json,
            :related_platforms_json, :related_assets_json, :related_deals_json,
            :ir_contact, :notes, :last_updated, :raw_json
        )
    """, {
        "id": c["id"],
        "name": c["name"],
        "ticker": c.get("ticker"),
        "listing_venue": c.get("listing_venue"),
        "country_hq": c.get("country_hq"),
        "employees": str(c.get("employees") or ""),
        "market_cap_usd_m": c.get("market_cap_usd_m"),
        "market_cap_as_of": str(c.get("market_cap_as_of") or ""),
        "cash_position_usd_m": c.get("cash_position_usd_m"),
        "cash_runway_quarters": c.get("cash_runway_quarters"),
        "debt_usd_m": c.get("debt_usd_m"),
        "ifrs_or_gaap": c.get("ifrs_or_gaap"),
        "governance_notes": c.get("governance_notes"),
        "m_and_a_protections_json": _j(c.get("m_and_a_protections")),
        "related_platforms_json": _j(c.get("related_platforms")),
        "related_assets_json": _j(c.get("related_assets")),
        "related_deals_json": _j(c.get("related_deals")),
        "ir_contact": c.get("ir_contact"),
        "notes": c.get("notes"),
        "last_updated": str(c.get("last_updated", "")),
        "raw_json": json.dumps(c, default=str),
    })


def insert_score(cur, entity_type: str, entity_id: str, dim: str, s: dict):
    cur.execute("""
        INSERT INTO scores VALUES (
            :entity_type, :entity_id, :dimension, :value, :rationale,
            :confidence, :scored_at, :scorer, :inherited_from
        )
    """, {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "dimension": dim,
        "value": s.get("value"),
        "rationale": s.get("rationale"),
        "confidence": s.get("confidence"),
        "scored_at": str(s.get("scored_at", "")),
        "scorer": s.get("scorer"),
        "inherited_from": s.get("inherited_from"),
    })
    # Also append to history
    cur.execute("""
        INSERT INTO scores_history VALUES (
            :entity_type, :entity_id, :dimension, :value, :rationale,
            :confidence, :scored_at, :scorer, :recorded_at
        )
    """, {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "dimension": dim,
        "value": s.get("value"),
        "rationale": s.get("rationale"),
        "confidence": s.get("confidence"),
        "scored_at": str(s.get("scored_at", "")),
        "scorer": s.get("scorer"),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    print("Building SQLite database from YAML...")

    platforms = load_yaml_dir(DATA_DIR / "platforms")
    print(f"  {len(platforms):3d} platforms")
    for p in platforms:
        insert_platform(cur, p)

    assets = load_yaml_dir(DATA_DIR / "assets")
    print(f"  {len(assets):3d} assets")
    for a in assets:
        insert_asset(cur, a)

    deals = load_yaml_dir(DATA_DIR / "deals")
    print(f"  {len(deals):3d} deals")
    for d in deals:
        insert_deal(cur, d)

    trials = load_yaml_dir(DATA_DIR / "trials")
    print(f"  {len(trials):3d} trials")
    for t in trials:
        insert_trial(cur, t)

    ip_positions = load_yaml_dir(DATA_DIR / "ip")
    print(f"  {len(ip_positions):3d} ip records")
    for ip in ip_positions:
        insert_ip(cur, ip)

    companies = load_yaml_dir(DATA_DIR / "companies")
    print(f"  {len(companies):3d} companies")
    for c in companies:
        insert_company(cur, c)

    conn.commit()
    conn.close()

    size_kb = DB_PATH.stat().st_size // 1024
    print(f"Done. {DB_PATH} ({size_kb} KB)")


if __name__ == "__main__":
    main()
