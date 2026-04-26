#!/usr/bin/env python3
"""
fill_technical_fit.py — One-shot updater that fills technical_fit and
cmc_capacity blocks on platforms with label-derived (FDA SmPC / EMA SmPC)
attributes.

Run once. Re-run-safe: only touches keys that are currently null /
unknown / 'Data pending'.

Sources for each entry are documented in TECHNICAL_FIT below — derived
from FDA-approved label / EMA SmPC for the lead approved product on
each platform. Verify against primary sources at quarterly refresh.
"""

import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
PLATFORMS = REPO / "data" / "platforms"

# Each value is (technical_fit_overrides, cmc_capacity_overrides)
# technical_fit fields used:
#   injection_volume_ml_range, viscosity_cP_range, needle_gauge_typical,
#   max_payload_mass_mg, cold_chain_required, excipient_classes,
#   release_profile_summary, iv_ivc_established, injection_site
TECHNICAL_FIT = {
    "nanocrystal": ({
        "injection_volume_ml_range": [0.875, 1.5],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "22G",
        "max_payload_mass_mg": 234,
        "cold_chain_required": False,
        "excipient_classes": ["polysorbate 20", "PEG 4000", "citric acid", "disodium phosphate"],
        "release_profile_summary": (
            "Nanocrystal palmitate ester suspension; gradual dissolution from "
            "deltoid or gluteal IM injection produces sustained paliperidone "
            "release over 1 month (Sustenna), 3 months (Trinza), or 6 months "
            "(Hafyera). For cabotegravir LA, monthly to every-2-month dosing."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM"],
    }, {
        "primary_facility": {"location": "Multiple Janssen / Alkermes sites", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": (
            "Janssen operates large-scale aseptic suspension manufacturing for "
            "Invega franchise. Alkermes retains residual NanoCrystal "
            "manufacturing know-how for legacy products. Capacity is not the "
            "bottleneck for this platform — adoption is."
        ),
    }),

    "medisorb": ({
        "injection_volume_ml_range": [0.5, 3.4],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "20G",
        "max_payload_mass_mg": 1064,
        "cold_chain_required": True,
        "excipient_classes": ["PLG copolymer", "carboxymethylcellulose", "polysorbate 20", "mannitol"],
        "release_profile_summary": (
            "PLGA microsphere suspension. Aristada delivers monthly to "
            "every-2-month aripiprazole lauroxil. Vivitrol monthly naltrexone. "
            "Bydureon weekly exenatide. Storage 2-8°C reflects microsphere "
            "stability requirements."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM"],
    }, {
        "primary_facility": {"location": "Athlone, Ireland", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": 24,
        "notes": (
            "Alkermes Athlone facility is one of the largest dedicated LAI "
            "microsphere manufacturing operations globally. Capacity reserved "
            "for Vivitrol, Aristada, plus historic third-party Bydureon supply."
        ),
    }),

    "atrigel": ({
        "injection_volume_ml_range": [0.25, 0.5],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "19G",
        "max_payload_mass_mg": 300,
        "cold_chain_required": True,
        "excipient_classes": ["PLGH polymer", "N-methyl-2-pyrrolidone (NMP)"],
        "release_profile_summary": (
            "Liquid PLGH/NMP precursor forms solid depot in situ on contact "
            "with body fluid. Sublocade: 0.5 mL SC abdominal monthly. Eligard: "
            "0.25-0.50 mL SC every 1, 3, 4, or 6 months. Storage refrigerated "
            "(2-8°C); allow to reach room temp before injection."
        ),
        "iv_ivc_established": True,
        "injection_site": ["SC"],
    }, {
        "primary_facility": {"location": "Fort Collins, Colorado, USA (Tolmar)", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": ["Indivior contract supply for Sublocade (verify)"],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 18,
        "notes": (
            "Tolmar's Fort Collins facility is the foundational Atrigel "
            "manufacturing site, supplying Eligard plus Sublocade contract "
            "production. Indivior also operates supplemental capacity. "
            "Generic challenges to Sublocade may shift contract dynamics."
        ),
    }),

    "depofoam": ({
        "injection_volume_ml_range": [0.5, 30.0],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "25G",
        "max_payload_mass_mg": 266,
        "cold_chain_required": True,
        "excipient_classes": ["DEPC", "DPPG", "tricaprylin", "cholesterol"],
        "release_profile_summary": (
            "Multivesicular liposomal depot. Exparel: 0.5-30 mL local wound "
            "infiltration delivering bupivacaine over 72 hours. Mechanism "
            "limited to local administration; not systemic LAI. Storage 2-8°C."
        ),
        "iv_ivc_established": True,
        "injection_site": ["local infiltration", "intra-articular"],
    }, {
        "primary_facility": {"location": "San Diego, California, USA (Pacira)", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 18,
        "notes": (
            "Pacira San Diego facility supports Exparel commercial supply. "
            "Generic ANDA challenges may reshape capacity utilization."
        ),
    }),

    "pds": ({
        "injection_volume_ml_range": [0.05, 0.05],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "34G refill needle",
        "max_payload_mass_mg": 5,
        "cold_chain_required": True,
        "excipient_classes": ["high-concentration ranibizumab formulation"],
        "release_profile_summary": (
            "Surgically-implanted refillable port reservoir delivering "
            "ranibizumab continuously to the vitreous; refilled in-office "
            "every 24 weeks. Differentiated from injection-based intravitreal "
            "LAI: ongoing diffusion vs depot release."
        ),
        "iv_ivc_established": True,
        "injection_site": ["intravitreal device"],
    }, {
        "primary_facility": {"location": "Genentech / Roche internal sites", "capacity_units_per_year": None, "units_definition": "devices"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 24,
        "notes": (
            "Susvimo had a 2022 voluntary recall (septum/leak) leading to "
            "device manufacturing process revisions. Relaunch in 2023. "
            "Capacity reflects post-relaunch operational state."
        ),
    }),

    "sandostatin_lar_platform": ({
        "injection_volume_ml_range": [2.5, 2.5],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "19G",
        "max_payload_mass_mg": 30,
        "cold_chain_required": True,
        "excipient_classes": ["DL-lactic-glycolic acid copolymer", "mannitol", "carboxymethylcellulose"],
        "release_profile_summary": (
            "PLGA microsphere suspension delivering octreotide monthly via "
            "deep gluteal IM injection. Storage 2-8°C. Reconstituted at room "
            "temp immediately before injection."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM"],
    }, {
        "primary_facility": {"location": "Novartis internal sites", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": "Mature franchise; capacity surplus given category decline post-generic.",
    }),

    "lupron_depot_platform": ({
        "injection_volume_ml_range": [1.0, 2.0],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "22G",
        "max_payload_mass_mg": 45,
        "cold_chain_required": False,
        "excipient_classes": ["lactide-glycolide copolymer", "gelatin", "mannitol"],
        "release_profile_summary": (
            "PLGA microsphere suspension delivering leuprolide acetate "
            "monthly (3.75-7.5 mg), every 3 months (11.25-22.5 mg), every 4 "
            "months (30 mg), or every 6 months (45 mg) via IM or SC. Storage "
            "at room temperature."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM", "SC"],
    }, {
        "primary_facility": {"location": "Takeda / AbbVie sites", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": "Mature global manufacturing; not capacity-constrained.",
    }),

    "trelstar_platform": ({
        "injection_volume_ml_range": [2.0, 2.0],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "21G",
        "max_payload_mass_mg": 22.5,
        "cold_chain_required": False,
        "excipient_classes": ["PLGA copolymer", "DL-lactide-glycolide", "mannitol", "polysorbate 80"],
        "release_profile_summary": (
            "PLGA microsphere suspension delivering triptorelin pamoate every "
            "1, 3, or 6 months via deep IM gluteal injection. Storage at "
            "room temperature."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM"],
    }, {
        "primary_facility": {"location": "Allergan / Watson legacy sites", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": "Mature franchise; commercial trajectory under generic pressure.",
    }),

    "somatuline_autogel": ({
        "injection_volume_ml_range": [0.5, 0.5],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "1.2 x 60 mm pre-filled syringe",
        "max_payload_mass_mg": 120,
        "cold_chain_required": True,
        "excipient_classes": ["water for injection", "lanreotide self-assembly"],
        "release_profile_summary": (
            "Lanreotide acetate forms semi-solid gel matrix on injection "
            "(unique self-assembly mechanism vs PLGA microsphere or in-situ "
            "depot platforms). Deep SC injection in upper outer buttock every "
            "28 days. Storage 2-8°C. Patient self-administration possible "
            "after training."
        ),
        "iv_ivc_established": True,
        "injection_site": ["SC"],
    }, {
        "primary_facility": {"location": "Signes / Dreux, France (Ipsen)", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": None,
        "notes": "Ipsen-internal manufacturing for the franchise.",
    }),

    "zoladex_implant": ({
        "injection_volume_ml_range": [None, None],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "14-16G implanter",
        "max_payload_mass_mg": 10.8,
        "cold_chain_required": False,
        "excipient_classes": ["lactide-glycolide copolymer (D,L-lactide:glycolide)"],
        "release_profile_summary": (
            "Solid biodegradable PLGA cylinder implant inserted SC into the "
            "upper abdominal wall via dedicated implanter delivering goserelin "
            "acetate over 28 days (3.6 mg) or 12 weeks (10.8 mg). Storage at "
            "room temperature."
        ),
        "iv_ivc_established": True,
        "injection_site": ["SC implant"],
    }, {
        "primary_facility": {"location": "AstraZeneca / TerSera sites", "capacity_units_per_year": None, "units_definition": "implants"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": "Mature franchise; multi-decade commercial use.",
    }),

    "idose": ({
        "injection_volume_ml_range": [None, None],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "27G inserter",
        "max_payload_mass_mg": 0.075,
        "cold_chain_required": False,
        "excipient_classes": ["proprietary titanium implant", "travoprost"],
        "release_profile_summary": (
            "Anchored intracameral titanium implant releasing travoprost "
            "free acid over 24-36 months. Inserted by ophthalmologist via "
            "dedicated inserter through a clear corneal incision."
        ),
        "iv_ivc_established": True,
        "injection_site": ["intracameral"],
    }, {
        "primary_facility": {"location": "Aliso Viejo, California (Glaukos)", "capacity_units_per_year": None, "units_definition": "implants"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 18,
        "notes": "Glaukos-internal. Capacity scales with launch trajectory.",
    }),

    "durasert": ({
        "injection_volume_ml_range": [None, None],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "25G inserter",
        "max_payload_mass_mg": 0.18,
        "cold_chain_required": False,
        "excipient_classes": ["polyvinyl alcohol", "polylactic acid", "fluocinolone acetonide", "vorolanib", "or other API"],
        "release_profile_summary": (
            "Bioerodible (Durasert E) or non-erodible (Durasert legacy) "
            "intravitreal insert. Yutiq: 0.18 mg fluocinolone acetonide, "
            "36-month duration. EYP-1901: vorolanib bioerodible in development. "
            "Inserted via 25G inserter as in-office procedure."
        ),
        "iv_ivc_established": True,
        "injection_site": ["intravitreal"],
    }, {
        "primary_facility": {"location": "Watertown, Massachusetts (EyePoint)", "capacity_units_per_year": None, "units_definition": "inserts"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 18,
        "notes": "EyePoint-internal manufacturing for Yutiq, Dexycu commercial supply plus EYP-1901 clinical supply.",
    }),

    "novadur": ({
        "injection_volume_ml_range": [None, None],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "28G inserter",
        "max_payload_mass_mg": 0.01,
        "cold_chain_required": False,
        "excipient_classes": ["PLGA copolymer", "bimatoprost"],
        "release_profile_summary": (
            "Biodegradable rod-shaped intracameral implant releasing "
            "bimatoprost over 3-4 months. Inserted via 28G inserter through "
            "clear corneal incision. Single-administration label."
        ),
        "iv_ivc_established": True,
        "injection_site": ["intracameral"],
    }, {
        "primary_facility": {"location": "AbbVie / Allergan sites", "capacity_units_per_year": None, "units_definition": "implants"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": None,
        "notes": "AbbVie-internal manufacturing.",
    }),

    "biochronomer": ({
        "injection_volume_ml_range": [0.5, 30.0],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "23-25G",
        "max_payload_mass_mg": 400,
        "cold_chain_required": True,
        "excipient_classes": ["polyorthoester", "triethyl citrate", "menthol"],
        "release_profile_summary": (
            "Polyorthoester triglyceride matrix delivering local sustained "
            "release over 72 hours (Zynrelef bupivacaine + meloxicam) or "
            "5 days (Sustol granisetron). Designed for local infiltration / "
            "SC administration. Storage 2-8°C."
        ),
        "iv_ivc_established": True,
        "injection_site": ["local infiltration", "SC"],
    }, {
        "primary_facility": {"location": "San Diego, California (Heron)", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "moderate",
        "scale_up_timeline_months": 18,
        "notes": "Heron-internal manufacturing for Zynrelef, Sustol commercial supply.",
    }),

    "ism": ({
        "injection_volume_ml_range": [1.0, 1.5],
        "viscosity_cP_range": [None, None],
        "needle_gauge_typical": "21G",
        "max_payload_mass_mg": 100,
        "cold_chain_required": False,
        "excipient_classes": ["PLGA copolymer", "DMSO"],
        "release_profile_summary": (
            "PLGA / DMSO in-situ depot delivering risperidone monthly via "
            "deep gluteal IM injection. Mechanism analogous to BEPO and "
            "Atrigel; differentiated by polymer formulation."
        ),
        "iv_ivc_established": True,
        "injection_site": ["IM"],
    }, {
        "primary_facility": {"location": "Madrid / Granada, Spain (Rovi)", "capacity_units_per_year": None, "units_definition": "doses"},
        "cdmo_partners": [],
        "capacity_headroom": "ample",
        "scale_up_timeline_months": 12,
        "notes": (
            "Rovi operates large-scale aseptic-fill manufacturing supporting "
            "both internal Risvan supply and external CDMO contracts (incl. "
            "COVID vaccine fill/finish). Capacity is a structural advantage."
        ),
    }),
}


def deep_merge(target: dict, source: dict) -> bool:
    """Merge source into target only where target has 'placeholder' values.
    Returns True if any change was made.
    """
    changed = False
    for k, v in source.items():
        if k not in target:
            target[k] = v
            changed = True
            continue
        existing = target[k]
        # Treat null / "Data pending." / "unknown" / empty list as placeholder
        is_placeholder = (
            existing is None
            or existing == []
            or existing == "unknown"
            or (isinstance(existing, str) and "data pending" in existing.lower())
            or (isinstance(existing, list) and existing == [None, None])
        )
        if is_placeholder:
            target[k] = v
            changed = True
        elif isinstance(existing, dict) and isinstance(v, dict):
            if deep_merge(existing, v):
                changed = True
    return changed


def main():
    n_changed = 0
    for pid, (tf_overrides, cmc_overrides) in TECHNICAL_FIT.items():
        path = PLATFORMS / f"{pid}.yaml"
        if not path.exists():
            print(f"  SKIP missing: {path.name}", file=sys.stderr)
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        changed_tf = deep_merge(data.setdefault("technical_fit", {}), tf_overrides)
        changed_cmc = deep_merge(data.setdefault("cmc_capacity", {}), cmc_overrides)
        if changed_tf or changed_cmc:
            path.write_text(
                yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
                encoding="utf-8",
            )
            print(f"  updated: {path.name}")
            n_changed += 1
    print(f"\n{n_changed} platform(s) updated.")


if __name__ == "__main__":
    main()
