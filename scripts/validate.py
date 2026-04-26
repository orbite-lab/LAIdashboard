#!/usr/bin/env python3
"""
validate.py — Check YAML schema integrity across all data files.

Flags:
- Missing required fields
- Orphaned references (e.g., asset.platform_id, encumbrance.deal_id)
- Scores without rationale or confidence
- Taxonomy violations
- Low-confidence high scores (potential overclaim)
- v1 schema: trials without nct_id/asset_id, ip without platform/asset linkage,
  companies missing essentials, encumbrances pointing at non-existent deals.

Exit codes:
    0 — all clean
    1 — errors found
    2 — warnings only (informational)

Usage:
    python scripts/validate.py
"""

import sys
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("Missing dependency: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

VALID_MECHANISMS = {
    "in_situ_depot", "microsphere", "nanoparticle", "implant",
    "drug_conjugate", "liposome_depot", "oil_solution",
    "peptide_self_assembly", "other",
}
VALID_DURATION_BUCKETS = {"short", "medium", "long", "ultra_long"}
VALID_PAYLOAD_CLASSES = {
    "small_molecule", "peptide", "protein", "biologic", "nucleic_acid",
}
VALID_INDICATION_CODES = {
    "psych", "addiction", "hiv", "oncology", "endocrine", "ophthalmology",
    "pain", "cns_neuro", "metabolic", "other",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_DISCLOSURE = {"full", "partial", "minimal"}
VALID_POSTURE = {"true", "false", "selective", "unknown"}
VALID_HEADROOM = {"ample", "moderate", "tight", "unknown"}
VALID_TRIAL_STATUS = {
    "planning", "enrolling", "active", "completed",
    "terminated", "readout-pending",
}
VALID_PLATFORM_DIMS = {"tech", "ip", "dealability", "availability"}
VALID_ASSET_DIMS = {"tech", "clinical", "ip", "dealability", "regulatory"}

errors = []
warnings = []


def err(msg: str):
    errors.append(msg)


def warn(msg: str):
    warnings.append(msg)


def load_tagged(subdir: str) -> dict[str, dict]:
    path = DATA_DIR / subdir
    out = {}
    if not path.exists():
        return out
    for f in sorted(path.glob("*.yaml")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data is None:
                continue
            if "id" in data:
                data["_source_file"] = f.name
                if data["id"] in out:
                    err(f"{f.name}: duplicate id '{data['id']}'")
                else:
                    out[data["id"]] = data
            else:
                err(f"{f.name}: missing 'id'")
        except yaml.YAMLError as e:
            err(f"{f.name}: YAML error: {e}")
    return out


def check_score_block(path_label: str, scores: dict, allowed_dims: set | None = None):
    """Every score must have value, rationale, confidence."""
    if not scores:
        return
    for dim, s in scores.items():
        if allowed_dims is not None and dim not in allowed_dims:
            warn(f"{path_label}: score dimension '{dim}' not in {sorted(allowed_dims)}")
        if not isinstance(s, dict):
            err(f"{path_label}: score for '{dim}' is not a mapping")
            continue
        if "value" not in s:
            err(f"{path_label}: score.{dim} missing 'value'")
        elif not isinstance(s["value"], int) or not (1 <= s["value"] <= 5):
            err(f"{path_label}: score.{dim}.value must be integer 1-5, got {s['value']!r}")
        if not s.get("rationale"):
            err(f"{path_label}: score.{dim} missing 'rationale' (mandatory per rubric)")
        conf = s.get("confidence")
        if conf not in VALID_CONFIDENCE:
            err(f"{path_label}: score.{dim}.confidence must be one of {VALID_CONFIDENCE}, got {conf!r}")
        if conf == "low" and s.get("value", 0) >= 4:
            warn(f"{path_label}: score.{dim} has value {s['value']} with low confidence — review")


def validate_platform(p: dict, deals: dict, companies: dict):
    label = f"platforms/{p.get('_source_file', p['id'])}"
    required = ["id", "name", "company", "mechanism",
                "duration_bucket", "duration_range_days", "payload_classes",
                "ip_core_expiry_year", "ip_continuation_strategy", "ip_fto_concerns"]
    for r in required:
        if p.get(r) in (None, ""):
            err(f"{label}: missing required field '{r}'")
    if p.get("mechanism") not in VALID_MECHANISMS:
        err(f"{label}: mechanism '{p.get('mechanism')}' not in taxonomy")
    if p.get("duration_bucket") not in VALID_DURATION_BUCKETS:
        err(f"{label}: duration_bucket '{p.get('duration_bucket')}' not in taxonomy")
    for pc in p.get("payload_classes") or []:
        if pc not in VALID_PAYLOAD_CLASSES:
            err(f"{label}: payload_class '{pc}' not in taxonomy")
    check_score_block(label, p.get("scores"), VALID_PLATFORM_DIMS)
    for ind, s in (p.get("indication_fit") or {}).items():
        if ind not in VALID_INDICATION_CODES:
            err(f"{label}: indication_fit key '{ind}' not in taxonomy")
        check_score_block(f"{label}.indication_fit", {ind: s})

    # Partnering posture (v1) — soft required, warn only if missing entirely
    posture = p.get("partnering_posture")
    if posture:
        otp = str(posture.get("open_to_partnering")).lower()
        if otp not in VALID_POSTURE:
            err(f"{label}: partnering_posture.open_to_partnering '{otp}' invalid; expected {VALID_POSTURE}")

    # Encumbrances must reference real deals
    for enc in p.get("encumbrances") or []:
        did = enc.get("deal_id")
        if did and did not in deals:
            err(f"{label}: encumbrance references unknown deal_id '{did}'")
        for ind in enc.get("indications") or []:
            if ind not in VALID_INDICATION_CODES:
                err(f"{label}: encumbrance indication '{ind}' not in taxonomy")

    # CMC capacity — validate enum
    cmc = p.get("cmc_capacity") or {}
    if cmc and cmc.get("capacity_headroom") not in VALID_HEADROOM | {None}:
        err(f"{label}: cmc_capacity.capacity_headroom '{cmc.get('capacity_headroom')}' invalid; expected {VALID_HEADROOM}")

    # Company linkage — soft check
    cid = p.get("company_id")
    if cid and cid not in companies:
        warn(f"{label}: company_id '{cid}' does not match any company in data/companies/")


def validate_asset(a: dict, platforms: dict, trials: dict, deals: dict):
    label = f"assets/{a.get('_source_file', a['id'])}"
    required = ["id", "name", "platform_id", "owning_company", "indications"]
    for r in required:
        if a.get(r) in (None, "", []):
            err(f"{label}: missing required field '{r}'")
    pid = a.get("platform_id")
    if pid and pid not in platforms:
        err(f"{label}: platform_id '{pid}' does not match any platform in data/platforms/")
    for ind in a.get("indications") or []:
        code = ind.get("code")
        if code not in VALID_INDICATION_CODES:
            err(f"{label}: indication code '{code}' not in taxonomy")
    check_score_block(label, a.get("scores"), VALID_ASSET_DIMS)

    # Trial linkage
    for t in a.get("primary_trials") or []:
        tid = t.get("trial_id")
        if tid and tid not in trials:
            warn(f"{label}: primary_trials references unknown trial_id '{tid}'")

    # Primary deal linkage
    pdid = a.get("primary_deal_id")
    if pdid and pdid not in deals:
        warn(f"{label}: primary_deal_id '{pdid}' does not match any deal")


def validate_deal(d: dict, platforms: dict, assets: dict):
    label = f"deals/{d.get('_source_file', d['id'])}"
    required = ["id", "deal_type", "status", "licensor", "licensee",
                "description", "announced_date", "disclosure_quality",
                "source_urls"]
    for r in required:
        if d.get(r) in (None, "", []):
            err(f"{label}: missing required field '{r}'")
    if d.get("disclosure_quality") not in VALID_DISCLOSURE:
        err(f"{label}: disclosure_quality '{d.get('disclosure_quality')}' invalid")
    aid = d.get("asset_id")
    pid = d.get("platform_id")
    if aid and aid not in assets:
        warn(f"{label}: asset_id '{aid}' does not match any asset (may be preclinical/undisclosed)")
    if pid and pid not in platforms:
        err(f"{label}: platform_id '{pid}' does not match any platform")
    for ind in d.get("indications_covered") or []:
        if ind not in VALID_INDICATION_CODES:
            err(f"{label}: indications_covered code '{ind}' not in taxonomy")


def validate_trial(t: dict, assets: dict):
    label = f"trials/{t.get('_source_file', t['id'])}"
    # phase is optional — CT.gov reports null for observational/PMS/registry trials
    required = ["id", "nct_id", "asset_id", "indication", "sponsor", "status"]
    for r in required:
        if t.get(r) in (None, ""):
            err(f"{label}: missing required field '{r}'")
    aid = t.get("asset_id")
    if aid and aid not in assets:
        warn(f"{label}: asset_id '{aid}' does not match any asset")
    if t.get("indication") not in VALID_INDICATION_CODES:
        err(f"{label}: indication '{t.get('indication')}' not in taxonomy")
    if t.get("status") not in VALID_TRIAL_STATUS:
        err(f"{label}: status '{t.get('status')}' invalid; expected {VALID_TRIAL_STATUS}")
    if t.get("phase") not in {1, 2, 3, 4, None}:
        err(f"{label}: phase '{t.get('phase')}' invalid")


def validate_ip(ip: dict, platforms: dict, assets: dict):
    label = f"ip/{ip.get('_source_file', ip['id'])}"
    required = ["id", "patent_number", "jurisdiction", "assignee",
                "expiry_date", "claim_type"]
    for r in required:
        if ip.get(r) in (None, ""):
            err(f"{label}: missing required field '{r}'")
    pid = ip.get("platform_id")
    aid = ip.get("asset_id")
    if pid and pid not in platforms:
        err(f"{label}: platform_id '{pid}' does not match any platform")
    if aid and aid not in assets:
        warn(f"{label}: asset_id '{aid}' does not match any asset")
    if not pid and not aid:
        warn(f"{label}: neither platform_id nor asset_id set — IP record orphaned")


def validate_company(c: dict):
    label = f"companies/{c.get('_source_file', c['id'])}"
    required = ["id", "name", "country_hq"]
    for r in required:
        if c.get(r) in (None, ""):
            err(f"{label}: missing required field '{r}'")


def main():
    platforms = load_tagged("platforms")
    assets = load_tagged("assets")
    deals = load_tagged("deals")
    trials = load_tagged("trials")
    ip_positions = load_tagged("ip")
    companies = load_tagged("companies")

    for p in platforms.values():
        validate_platform(p, deals, companies)
    for a in assets.values():
        validate_asset(a, platforms, trials, deals)
    for d in deals.values():
        validate_deal(d, platforms, assets)
    for t in trials.values():
        validate_trial(t, assets)
    for ip in ip_positions.values():
        validate_ip(ip, platforms, assets)
    for c in companies.values():
        validate_company(c)

    print(
        f"Validated: {len(platforms)} platforms, {len(assets)} assets, "
        f"{len(deals)} deals, {len(trials)} trials, {len(ip_positions)} ip, "
        f"{len(companies)} companies"
    )
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print(f"  X {e}")
    if warnings:
        print(f"\n{len(warnings)} WARNING(S):")
        for w in warnings:
            print(f"  ! {w}")
    if not errors and not warnings:
        print("All clean.")
        sys.exit(0)
    sys.exit(1 if errors else 2)


if __name__ == "__main__":
    main()
