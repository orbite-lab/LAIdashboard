#!/usr/bin/env python3
"""
scrape_clinicaltrials.py — Pull structured LAI trial data from
ClinicalTrials.gov API v2 and emit data/trials/<slug>.yaml stubs.

Restricted to long-acting injectable / depot / implant scope. Filters out
obviously out-of-scope hits (oral ER, transdermal, vaccines, half-life-
engineered biologics that aren't directly competing with depot LAI).

Usage:
    python scripts/scrape_clinicaltrials.py
    python scripts/scrape_clinicaltrials.py --asset uzedy
    python scripts/scrape_clinicaltrials.py --dry-run

Config: see ASSET_QUERIES at top of file. Each entry maps a tracker asset_id
to (sponsor, search terms) used against the CT.gov API.
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRIALS_DIR = REPO / "data" / "trials"
ASSETS_DIR = REPO / "data" / "assets"

# (asset_id, sponsor_substring, intervention_term, indication_code,
#  expected_phases, max_results)
# Keep tightly LAI-scoped — explicit intervention strings rule out
# oral, transdermal, and short-acting trials of the same molecule.
ASSET_QUERIES = [
    ("uzedy",            "Teva",       "TV-46000 OR risperidone long-acting OR risperidone subcutaneous",                "psych",         {2,3,4}, 10),
    ("mdc_tjk_olanzapine","Teva",      "TV-44749 OR TV-749 OR olanzapine subcutaneous OR mdc-TJK",                       "psych",         {2,3},   10),
    ("brixadi",          "Camurus",    "CAM2038 OR buprenorphine subcutaneous extended-release OR Brixadi OR Buvidal",   "addiction",     {2,3,4}, 10),
    ("buvidal",          "Camurus",    "Buvidal OR CAM2038 OR buprenorphine subcutaneous monthly",                       "addiction",     {2,3,4}, 10),
    ("cam2029",          "Camurus",    "CAM2029 OR octreotide subcutaneous depot",                                       "endocrine",     {2,3},   10),
    ("cam2032",          "Camurus",    "CAM2032 OR setmelanotide long-acting OR setmelanotide depot",                    "endocrine",     {1,2,3}, 10),
    ("apretude",         "ViiV",       "cabotegravir long-acting injection OR Apretude OR HPTN 083 OR HPTN 084",         "hiv",           {2,3,4}, 10),
    ("cabenuva",         "ViiV",       "cabotegravir rilpivirine long-acting OR Cabenuva OR ATLAS OR FLAIR",              "hiv",           {2,3,4}, 10),
    ("susvimo",          "Genentech",  "Susvimo OR ranibizumab port delivery OR ARCHWAY OR PORTAL",                      "ophthalmology", {2,3,4}, 10),
    ("vivitrol",         "Alkermes",   "Vivitrol OR naltrexone extended-release injection",                              "addiction",     {2,3,4}, 10),
    ("sublocade",        "Indivior",   "Sublocade OR RBP-6000 OR buprenorphine extended-release subcutaneous",            "addiction",     {2,3,4}, 10),
    ("invega_sustenna",  "Janssen",    "paliperidone palmitate monthly OR Invega Sustenna",                              "psych",         {2,3,4}, 10),
    ("invega_hafyera",   "Janssen",    "paliperidone palmitate 6-month OR Invega Hafyera",                               "psych",         {2,3,4}, 10),
    ("eligard",          "Tolmar",     "Eligard OR leuprolide acetate Atrigel OR leuprolide subcutaneous depot",         "oncology",      {3,4},   8),
    ("exparel",          "Pacira",     "Exparel OR bupivacaine liposomal",                                               "pain",          {3,4},   8),
    ("somatuline_depot", "Ipsen",      "Somatuline OR lanreotide autogel",                                               "endocrine",     {3,4},   8),
    ("sandostatin_lar",  "Novartis",   "Sandostatin LAR OR octreotide LAR",                                              "endocrine",     {3,4},   8),
]

# Negative filters — drop studies whose title strongly suggests out-of-scope
NEGATIVE_TITLE_PATTERNS = [
    r"\boral\b",
    r"\btablet\b",
    r"\bsublingual\b",
    r"\bbuccal\b",
    r"\btransdermal\b",
    r"\bpatch\b",
    r"\bvaccine\b",
    r"\binhalation\b",
    r"\binhaled\b",
]
NEG_RE = re.compile("|".join(NEGATIVE_TITLE_PATTERNS), re.IGNORECASE)


def fetch(query_term: str, page_size: int = 25) -> list[dict]:
    """Hit ClinicalTrials.gov API v2 and return a list of study protocol blocks."""
    base = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.term": query_term,
        "pageSize": str(page_size),
        "format": "json",
        "filter.overallStatus": (
            "NOT_YET_RECRUITING|RECRUITING|ACTIVE_NOT_RECRUITING|COMPLETED|"
            "TERMINATED|WITHDRAWN|UNKNOWN"
        ),
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read())
    return data.get("studies", [])


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:max_len]


def map_phase(phase_list: list[str] | None) -> int | None:
    """CT.gov reports 'PHASE1', 'PHASE2', 'PHASE3', 'PHASE4', 'PHASE1_PHASE2' etc."""
    if not phase_list:
        return None
    # Take the highest phase
    best = 0
    for p in phase_list:
        m = re.findall(r"PHASE(\d)", p.upper())
        for n in m:
            best = max(best, int(n))
    return best or None


def map_status(ct_status: str | None) -> str:
    """Map CT.gov overallStatus into our taxonomy."""
    if not ct_status:
        return "active"
    s = ct_status.upper()
    if s in ("NOT_YET_RECRUITING",):
        return "planning"
    if s in ("RECRUITING",):
        return "enrolling"
    if s in ("ACTIVE_NOT_RECRUITING",):
        return "active"
    if s in ("COMPLETED",):
        return "completed"
    if s in ("TERMINATED", "WITHDRAWN", "SUSPENDED"):
        return "terminated"
    return "active"


def map_control(arm_groups: list[dict] | None) -> str:
    """Heuristic: classify control arm from arm group labels."""
    if not arm_groups:
        return "null"
    labels = " ".join((a.get("label") or "").lower() for a in arm_groups)
    if "placebo" in labels:
        return "placebo"
    if "standard of care" in labels or "soc" in labels:
        return "SOC"
    # Multiple groups but no placebo/SOC → likely active comparator
    if len(arm_groups) > 1:
        return "active comparator"
    return "none"


def study_to_yaml(study: dict, asset_id: str, indication: str,
                  expected_phases: set[int]) -> tuple[str, dict] | None:
    """Convert a CT.gov study to our trial schema dict, or None if out-of-scope."""
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    status_mod = p.get("statusModule", {})
    design = p.get("designModule", {})
    desc = p.get("descriptionModule", {})
    arms = p.get("armsInterventionsModule", {})
    sponsor = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", "")

    nct_id = ident.get("nctId")
    title = ident.get("briefTitle") or ident.get("officialTitle") or ""

    # Out-of-scope filter on title
    if NEG_RE.search(title):
        return None

    phase = map_phase(design.get("phases"))
    if expected_phases and phase is not None and phase not in expected_phases:
        return None

    enrollment = (design.get("enrollmentInfo") or {}).get("count")
    primary_endpoints = p.get("outcomesModule", {}).get("primaryOutcomes") or []
    primary = "; ".join(o.get("measure", "") for o in primary_endpoints)[:500]
    arm_groups = arms.get("armGroups") or []
    control = map_control(arm_groups)

    start = (status_mod.get("startDateStruct") or {}).get("date")
    pcd = (status_mod.get("primaryCompletionDateStruct") or {}).get("date")
    overall = status_mod.get("overallStatus")

    # locations
    locs = p.get("contactsLocationsModule", {}).get("locations") or []
    countries = sorted({l.get("country") for l in locs if l.get("country")})

    slug = slugify(f"{asset_id}_{nct_id}".lower())
    record = {
        "id": slug,
        "nct_id": nct_id,
        "asset_id": asset_id,
        "indication": indication,
        "phase": phase,
        "n": enrollment,
        "design": (design.get("studyType") or "").title() or None,
        "primary_endpoint": primary or None,
        "control_arm": control,
        "sponsor": sponsor,
        "status": map_status(overall),
        "start_date": start,
        "expected_readout": pcd,
        "result": None,
        "geography": countries[:8] if countries else None,
        "source_urls": [f"https://clinicaltrials.gov/study/{nct_id}"],
        "notes": (
            f"Auto-imported from ClinicalTrials.gov on import date. "
            f"Title: {title}. Sponsor: {sponsor}. Verify scope against asset's "
            f"depot/LAI formulation before relying on this record."
        ),
        "last_updated": "2026-04-26",
    }
    return slug, record


def to_yaml(d: dict) -> str:
    """Minimal YAML emitter — enough for our schema, no external deps required."""
    out = []

    def emit(key, value, indent=0):
        pad = "  " * indent
        if value is None:
            out.append(f"{pad}{key}: null")
        elif isinstance(value, bool):
            out.append(f"{pad}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            out.append(f"{pad}{key}: {value}")
        elif isinstance(value, list):
            if not value:
                out.append(f"{pad}{key}: []")
            else:
                out.append(f"{pad}{key}:")
                for v in value:
                    if isinstance(v, str):
                        out.append(f"{pad}  - {json.dumps(v)}")
                    else:
                        out.append(f"{pad}  - {v}")
        elif isinstance(value, str):
            # Use block scalar for long/multi-line strings
            if "\n" in value or len(value) > 100:
                out.append(f"{pad}{key}: >")
                for line in value.split("\n"):
                    out.append(f"{pad}  {line}")
            else:
                # Always-quote to dodge YAML-special characters
                out.append(f"{pad}{key}: {json.dumps(value)}")
        else:
            out.append(f"{pad}{key}: {json.dumps(str(value))}")

    for k, v in d.items():
        emit(k, v)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", help="Restrict to one asset_id")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print proposed yaml writes without saving")
    ap.add_argument("--overwrite", action="store_true",
                    help="Overwrite existing trial yaml files")
    args = ap.parse_args()

    TRIALS_DIR.mkdir(parents=True, exist_ok=True)

    queries = ASSET_QUERIES
    if args.asset:
        queries = [q for q in queries if q[0] == args.asset]
        if not queries:
            print(f"Unknown asset_id: {args.asset}", file=sys.stderr)
            sys.exit(1)

    written = 0
    skipped = 0
    for asset_id, sponsor, terms, indication, phases, max_results in queries:
        # Use sponsor + terms together — CT.gov full-text matches both
        query = f"({terms}) AND {sponsor}"
        try:
            studies = fetch(query, page_size=max_results)
        except Exception as e:
            print(f"  ERROR for {asset_id}: {e}", file=sys.stderr)
            continue
        for s in studies:
            res = study_to_yaml(s, asset_id, indication, phases)
            if not res:
                skipped += 1
                continue
            slug, record = res
            target = TRIALS_DIR / f"{slug}.yaml"
            if target.exists() and not args.overwrite:
                skipped += 1
                continue
            yaml_str = to_yaml(record)
            if args.dry_run:
                print(f"--- {target.name} ---")
                print(yaml_str)
            else:
                target.write_text(yaml_str, encoding="utf-8")
                print(f"  wrote {target.name}")
            written += 1
    print(f"\n{written} written, {skipped} skipped (existing or out-of-scope).")


if __name__ == "__main__":
    main()
