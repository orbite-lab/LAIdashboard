#!/usr/bin/env python3
"""
validate.py — Check YAML schema integrity across all data files.

Flags:
- Missing required fields
- Orphaned references (e.g., asset.platform_id pointing to a non-existent platform)
- Scores without rationale or confidence
- Taxonomy violations (mechanism or indication code not in docs/taxonomy.md)
- Low-confidence high scores (potential overclaim)

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
    "drug_conjugate", "liposome_depot", "oil_solution", "other",
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

errors = []
warnings = []


def err(msg: str):
    errors.append(msg)


def warn(msg: str):
    warnings.append(msg)


def load_all(subdir: str) -> dict[str, dict]:
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
            if "id" not in data:
                err(f"{f.name}: missing required field 'id'")
                continue
            if data["id"] in out:
                err(f"{f.name}: duplicate id '{data['id']}'")
                continue
            out[data["id"]] = data
        except yaml.YAMLError as e:
            err(f"{f.name}: YAML parse error: {e}")
    return out


def check_score_block(path_label: str, scores: dict):
    """Every score must have value, rationale, confidence."""
    if not scores:
        return
    for dim, s in scores.items():
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
        # Warn on low-confidence high scores
        if conf == "low" and s.get("value", 0) >= 4:
            warn(f"{path_label}: score.{dim} has value {s['value']} with low confidence — review")


def validate_platform(p: dict):
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
    check_score_block(label, p.get("scores"))
    # indication_fit
    for ind, s in (p.get("indication_fit") or {}).items():
        if ind not in VALID_INDICATION_CODES:
            err(f"{label}: indication_fit key '{ind}' not in taxonomy")
        check_score_block(f"{label}.indication_fit", {ind: s})


def validate_asset(a: dict, platforms: dict):
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
    check_score_block(label, a.get("scores"))


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


def main():
    # Attach source filenames
    def load_tagged(subdir):
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
                    out[data["id"]] = data
                else:
                    err(f"{f.name}: missing 'id'")
            except yaml.YAMLError as e:
                err(f"{f.name}: YAML error: {e}")
        return out

    platforms = load_tagged("platforms")
    assets = load_tagged("assets")
    deals = load_tagged("deals")

    for p in platforms.values():
        validate_platform(p)
    for a in assets.values():
        validate_asset(a, platforms)
    for d in deals.values():
        validate_deal(d, platforms, assets)

    print(f"Validated: {len(platforms)} platforms, {len(assets)} assets, {len(deals)} deals")
    if errors:
        print(f"\n{len(errors)} ERROR(S):")
        for e in errors:
            print(f"  ✗ {e}")
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
