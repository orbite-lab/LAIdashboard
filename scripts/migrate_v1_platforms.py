#!/usr/bin/env python3
"""
migrate_v1_platforms.py — One-shot migration to add v1 schema fields to
all platforms not yet updated.

Adds defaults for:
  - partnering_posture
  - encumbrances (auto-derived from data/deals/ where possible)
  - technical_fit (placeholder; mark fields null; only adds block, not data)
  - cmc_capacity (placeholder)
  - scores.availability (default 3 if not set)
  - views.investor (mirrors tactbio_view)

Idempotent: skips platforms where a field already exists.
Run once. Re-run-safe.
"""

import sys
from pathlib import Path
from collections import defaultdict

import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"

# Read all deals to derive encumbrances
deals_by_platform: dict[str, list[dict]] = defaultdict(list)
for f in sorted((DATA / "deals").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    if d is None:
        continue
    pid = d.get("platform_id")
    if pid and d.get("exclusivity") == "exclusive" and d.get("status") == "active":
        deals_by_platform[pid].append(d)


def derive_encumbrances(pid: str) -> list[dict]:
    out = []
    for d in deals_by_platform.get(pid, []):
        out.append({
            "deal_id": d["id"],
            "indications": d.get("indications_covered") or [],
            "molecule_classes": ["undisclosed"],
            "compound_count_locked": None,
            "territory": d.get("territory") or "undisclosed",
            "exclusivity": d.get("exclusivity"),
            "expires": "deal-life",
        })
    return out


def default_posture(pid: str, has_encumbrances: bool) -> dict:
    return {
        "open_to_partnering": "selective" if has_encumbrances else "unknown",
        "open_indications": [],
        "closed_indications": [],
        "open_geographies": [],
        "closed_geographies": [],
        "last_partnering_signal": {
            "date": None,
            "type": "none",
            "description": "Data pending — populate from IR / press releases.",
        },
        "bd_contact_disclosed": False,
        "notes": "Auto-migrated v1 default. Refresh from primary sources.",
    }


def default_technical_fit() -> dict:
    return {
        "injection_volume_ml_range": [None, None],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": None,
        "max_payload_mass_mg": None,
        "cold_chain_required": None,
        "excipient_classes": [],
        "release_profile_summary": "Data pending.",
        "iv_ivc_established": None,
        "injection_site": [],
    }


def default_cmc_capacity() -> dict:
    return {
        "primary_facility": {
            "location": "unknown",
            "capacity_units_per_year": None,
            "units_definition": "doses",
        },
        "cdmo_partners": [],
        "capacity_headroom": "unknown",
        "scale_up_timeline_months": None,
        "notes": "Data pending.",
    }


def default_availability_score(pid: str, has_encumbrances: bool) -> dict:
    return {
        "value": 2 if has_encumbrances else 3,
        "rationale": (
            "Auto-migrated v1 default. Encumbrances detected from active "
            "exclusive deals — review and refine."
        ) if has_encumbrances else (
            "Auto-migrated v1 default. No active encumbrances detected; "
            "review partnering posture before publication."
        ),
        "confidence": "low",
        "scored_at": "2026-04-26",
        "scorer": "MIG",
    }


def migrate_one(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    p = yaml.safe_load(text)
    if p is None:
        return False
    pid = p["id"]
    changed = False

    encs = derive_encumbrances(pid)
    has_enc = bool(encs)

    if "partnering_posture" not in p:
        p["partnering_posture"] = default_posture(pid, has_enc)
        changed = True

    if "encumbrances" not in p:
        p["encumbrances"] = encs
        changed = True

    if "technical_fit" not in p:
        p["technical_fit"] = default_technical_fit()
        changed = True

    if "cmc_capacity" not in p:
        p["cmc_capacity"] = default_cmc_capacity()
        changed = True

    scores = p.setdefault("scores", {})
    if "availability" not in scores:
        scores["availability"] = default_availability_score(pid, has_enc)
        changed = True

    views = p.setdefault("views", {})
    if "investor" not in views and p.get("tactbio_view"):
        views["investor"] = p["tactbio_view"]
        changed = True
    if "partner" not in views:
        views["partner"] = (
            "Data pending — populate partner-view editorial. "
            "See partnering_posture and encumbrances for structured availability."
        )
        changed = True
    if "acquirer" not in views:
        views["acquirer"] = (
            "Data pending — populate acquirer-view editorial covering "
            "change-of-control terms, encumbrance map, and integration cost."
        )
        changed = True

    if "ip_records" not in p:
        p["ip_records"] = []
        changed = True

    if changed:
        path.write_text(
            yaml.dump(p, sort_keys=False, allow_unicode=True, width=88),
            encoding="utf-8",
        )
    return changed


def main():
    n_changed = 0
    for f in sorted((DATA / "platforms").glob("*.yaml")):
        if migrate_one(f):
            print(f"  migrated: {f.name}")
            n_changed += 1
    print(f"\nMigrated {n_changed} platform file(s).")


if __name__ == "__main__":
    main()
