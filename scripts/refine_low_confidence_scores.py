#!/usr/bin/env python3
"""
refine_low_confidence_scores.py — Replace v1-migration auto-default scores
and other low-confidence placeholders with evidence-backed values per the
rubric.

Three categories handled:
  (A) Platform availability scores — 22 entries auto-set to value=2 or 3
      with confidence=low by migrate_v1_platforms.py. Refined here based
      on owner posture, encumbrance reality, and partnering signals.
  (B) Specific platform / asset scores flagged as low confidence in the
      research queue — refined with evidence-based rationale.
  (C) Speculative indication_fit entries — either refined to medium
      confidence with specific rationale, or removed entirely (per rubric:
      "Omit indications where fit is irrelevant").

Idempotent. Re-run-safe.
"""

import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
PLATFORMS = REPO / "data" / "platforms"
ASSETS = REPO / "data" / "assets"

# ---------------------------------------------------------------------------
# (A) Availability score refinements per platform
# ---------------------------------------------------------------------------
# Format: platform_id -> (value, confidence, rationale)
AVAILABILITY = {
    "atrigel": (
        2, "medium",
        "Tolmar (private) commercializes Eligard directly and supplies Sublocade "
        "to Indivior under contract; no active platform-licensing posture for "
        "external partners. Atrigel core composition IP expired 2008 — manufacturing "
        "know-how is the residual moat. Available scope is narrow."
    ),
    "biochronomer": (
        3, "medium",
        "Heron commercializes Zynrelef and Sustol directly using Biochronomer; "
        "platform-licensing posture is selective given cash-runway pressure. "
        "Plausibly available for non-pain / non-CINV indications subject to "
        "Heron's strategic focus."
    ),
    "chroniject": (
        5, "high",
        "Oakwood Laboratories' core business model is partner-funded "
        "reformulation programs on Chroniject — the platform is structurally "
        "open to any pharma seeking microsphere LAI development. CDMO "
        "fee-for-service plus royalty structure standard."
    ),
    "depofoam": (
        1, "high",
        "Pacira BioSciences-internal asset for Exparel; mechanism niche to "
        "local administration limits transferability. No platform-licensing "
        "posture for external partners. Closed."
    ),
    "durasert": (
        3, "medium",
        "EyePoint actively partners Durasert: Alimera (Iluvien, since 2008), "
        "Astellas (2023 retinal TKI collaboration), Ono (2024 Asia EYP-1901 "
        "rights). Demonstrated openness to external partners in ophthalmic "
        "scope, though core wet-AMD economics retained internally."
    ),
    "idose": (
        1, "high",
        "Glaukos-internal commercial asset (iDose TR launched 2024); no "
        "platform-licensing signal. Closed for external partners."
    ),
    "ism": (
        3, "medium",
        "Rovi (founder-controlled mid-cap) retains EU commercialization for "
        "Risvan but has historically explored US/ROW out-licensing for the "
        "platform. Available scope outside EU psych is plausible; founder-"
        "family voting structure complicates platform-level deals."
    ),
    "lupron_depot_platform": (
        1, "high",
        "AbbVie/Takeda-internal mature franchise; no platform-licensing "
        "posture. Closed."
    ),
    "medisorb": (
        2, "medium",
        "Alkermes had an open NanoCrystal/Medisorb licensing posture in the "
        "1990s-2010s (Janssen, AstraZeneca/Lilly). Current focus is internal "
        "pipeline and existing royalty streams; no signal of active external "
        "partnering for new programs. Bydureon endocrine encumbrance limits "
        "incretin scope."
    ),
    "medusa": (
        4, "medium",
        "Adocia's commercial model is platform-licensing-driven (BioChaperone). "
        "After the 2017 Lilly partnership termination, Adocia has actively "
        "signaled openness to new partnerships; small-cap with cash-runway "
        "pressure increases willingness to deal. Track record warning: "
        "execution risk on partner programs."
    ),
    "nanocrystal": (
        2, "medium",
        "Alkermes-derived NanoCrystal IP estate is now Janssen-controlled for "
        "the active Invega and cabotegravir LAI franchises. ViiV/Janssen HIV "
        "scope is encumbered; Janssen psych scope is internal-only. Limited "
        "available scope absent specific Janssen out-licensing — none signaled."
    ),
    "nanozolid": (
        4, "medium",
        "LIDDS (Swedish micro-cap) actively shops NanoZolid for partnership; "
        "platform IP available across multiple oncology and intra-articular "
        "scopes. Cash-runway pressure increases willingness. Phase IIb data "
        "confirmation needed before tier-1 partnership likely materializes."
    ),
    "novadur": (
        1, "high",
        "AbbVie/Allergan-internal; supports Durysta commercial product. No "
        "platform-licensing posture for external partners. Closed."
    ),
    "oil_decanoate": (
        5, "high",
        "Off-patent generic vehicle technology; freely available to any "
        "manufacturer worldwide. No platform-level encumbrance possible. "
        "Multiple commercial decanoate antipsychotics globally."
    ),
    "pds": (
        1, "high",
        "Roche/Genentech-internal device technology supporting Susvimo. No "
        "platform-licensing posture. Closed."
    ),
    "perseris_platform": (
        1, "medium",
        "Indivior discontinued Perseris in July 2024. Platform basis is "
        "Atrigel-derived; no separate external availability outside the "
        "broader Atrigel platform. Effectively closed."
    ),
    "polyactiva": (
        4, "medium",
        "PolyActiva (private AU) has signaled active partnering discussions "
        "around PA5108 Phase 3 readiness through 2024-2025 (no executed "
        "exclusive deal disclosed). Platform structure is partnership-"
        "dependent given the company's clinical-stage scale."
    ),
    "probuphine": (
        1, "high",
        "Probuphine commercial product was discontinued post-2020. Titan "
        "Pharmaceuticals retains the ProNeura implant platform but commercial "
        "activity has wound down to maintenance. Effectively closed."
    ),
    "sandostatin_lar_platform": (
        1, "high",
        "Novartis-internal mature franchise post-Recordati Signifor divestiture. "
        "No platform-licensing posture for external partners."
    ),
    "signifor_lar_platform": (
        1, "high",
        "Recordati-internal post-2019 acquisition from Novartis. Rare-disease "
        "commercial focus does not include external platform licensing. "
        "Pasireotide indication scope encumbered."
    ),
    "somatuline_autogel": (
        1, "high",
        "Ipsen-internal franchise; founder-family majority control restricts "
        "external platform deals. Self-assembling peptide mechanism is "
        "uniquely Ipsen's manufacturing know-how. Closed."
    ),
    "spectrum": (
        4, "medium",
        "Foresee Pharmaceuticals' commercial model is explicitly platform-"
        "licensing-driven (Camcevi via Accord ex-US, Intas US, GenSci China). "
        "LHRH oncology scope is encumbered globally but other therapeutic "
        "areas remain open subject to Foresee BD bandwidth."
    ),
    "trelstar_platform": (
        2, "medium",
        "Debiopharm-Ipsen co-managed mature franchise (Decapeptyl/Trelstar). "
        "Triptorelin oncology scope commercially saturated; private-family "
        "ownership at Debiopharm and founder-family control at Ipsen "
        "restrict external platform-level deals."
    ),
    "zoladex_implant": (
        1, "high",
        "AstraZeneca-internal globally; US rights with TerSera. Off-patent "
        "commodity at this point. No platform-licensing posture."
    ),
}

# ---------------------------------------------------------------------------
# (B) Specific score refinements
# ---------------------------------------------------------------------------
# Format: (entity_kind, file_id, score_path, value, confidence, rationale)
# score_path is the dotted accessor inside the yaml ("scores.tech",
# "scores.ip", etc.) or "indication_fit.X"
SPECIFIC_SCORES = [
    # metsera platform tech — Phase 2b validates platform clinically
    ("platform", "metsera_lai", "scores.tech",
     3, "medium",
     "VESPER-1 Phase 2b (Sept 2025) confirmed HALO peptide-lipidation "
     "platform translates ultra-long PK (15-16 day half-life) into clinical "
     "weight loss — late-clinical platform validation. Multiple programs "
     "(MET-097, MET-233, MET-067) under same platform across GLP-1/amylin/"
     "GIP. Not yet commercial; Pfizer-led Phase 3 starting late 2025."),

    # PolyActiva platform IP
    ("platform", "polyactiva", "scores.ip",
     3, "medium",
     "Composition-of-matter patent estate for biodegradable polymer-rod "
     "intracameral implant filed mid-2010s; effective protection through "
     "~2035-2040 base. Private filing with limited public visibility, but "
     "company has stated FTO position is clear. Specific patent search "
     "would refine; estate is real but not exhaustively reviewed."),

    # PolyActiva platform dealability
    ("platform", "polyactiva", "scores.dealability",
     3, "medium",
     "Active partnership discussions disclosed by company since 2023 "
     "(no executed exclusive deal) signal genuine BD activity. Reference "
     "comp: Glaukos iDose-licensed precedents and AbbVie/Allergan Durysta "
     "establish that ophthalmic implant LAI commands tier-1 economics post-"
     "Phase-3 readout. Pre-pivotal so dealability is theoretical."),

    # CAM2032 clinical
    ("asset", "cam2032", "scores.clinical",
     2, "medium",
     "Setmelanotide approved (IMCIVREE) for rare genetic obesity establishes "
     "the molecule clinically. CAM2032 is the FluidCrystal-formulated long-"
     "acting variant in Phase 2 with Rhythm; weight-of-evidence supports "
     "feasibility but specific Phase 2 readout endpoints and dose-finding "
     "data are not publicly disclosed. Phase 3 timing dependent on Phase 2 "
     "outcome."),

    # CAM2032 IP
    ("asset", "cam2032", "scores.ip",
     3, "medium",
     "FluidCrystal platform IP (~2030 base, continuations through 2030+) "
     "plus Rhythm-partnered formulation patents covering the long-acting "
     "setmelanotide composition. Setmelanotide molecule IP is Rhythm-"
     "controlled; LAI formulation IP provides additional moat over the "
     "approved daily dosing form."),

    # PA5108 IP
    ("asset", "pa5108", "scores.ip",
     3, "medium",
     "PolyActiva platform IP (composition-of-matter for biodegradable rod "
     "implant) plus PA5108-specific formulation patents covering latanoprost "
     "loading and release profile. Effective protection adequate for first "
     "commercial cycle if Phase 3 succeeds; private company so detailed "
     "patent landscape less visible than for public peers."),

    # PA5108 dealability
    ("asset", "pa5108", "scores.dealability",
     2, "medium",
     "Pre-Phase-3 readout — partnership economics speculative. Reference "
     "comp: Glaukos iDose internal commercialization and AbbVie/Allergan "
     "Durysta acquisition history establish commercial value for ophthalmic "
     "implant LAI but PolyActiva private status and clinical-stage scale "
     "limit deal optionality until pivotal data lands."),

    # Risvan IP
    ("asset", "risvan", "scores.ip",
     3, "medium",
     "ISM platform IP (Rovi-controlled) plus asset-specific formulation "
     "patents covering the monthly risperidone in-situ depot. EU exclusivity "
     "supports current Risvan / Okedi commercial trajectory; US filing "
     "status uncertain so US IP scope speculative until ANDA / NDA path "
     "clarifies."),
]

# ---------------------------------------------------------------------------
# (C) Indication-fit refinements
# ---------------------------------------------------------------------------
# Three actions: REFINE keeps the score and updates rationale + confidence;
# REMOVE deletes the entry (rubric: "Omit indications where fit is irrelevant").

INDICATION_FIT_UPDATES = [
    # KEEP (refine to medium with specific rationale)
    ("bepo", "hiv", "REFINE", 3, "medium",
     "HIV LAI category dominated by ViiV cabotegravir (Cabenuva, Apretude) "
     "with 2-month dosing using nanocrystal mechanism. BEPO would need a "
     "molecule partner and structural advantage (longer duration, better "
     "tolerability) to compete. Mechanism is technically compatible but "
     "the high commercial bar makes BEPO HIV entry low-probability absent "
     "a tier-1 antiviral partner."),

    ("bepo", "oncology", "REFINE", 3, "medium",
     "AbbVie 2024 BEPO collaboration explicitly covers oncology among the "
     "six-program scope; specific molecule undisclosed. Mechanism compatible "
     "with hormonal LAI (LHRH-style) and small-molecule oncology agents. "
     "Encumbered to AbbVie; commercial fit moderate given Eligard/Lupron/"
     "Zoladex dominance in established LHRH oncology indications."),

    ("fluidcrystal", "oncology", "REFINE", 3, "medium",
     "Demonstrated peptide delivery via CAM2029 (octreotide for GEP-NETs in "
     "Phase 3) extends FluidCrystal into peptide oncology. CAM2032 (setmelanotide) "
     "addresses rare endocrine more than oncology proper. LHRH-class and "
     "newer peptide oncology agents technically feasible but commoditized "
     "incumbents (Eligard, Zoladex, Lupron) compress commercial fit."),

    ("ism", "endocrine", "REFINE", 3, "medium",
     "Rovi has disclosed letrozole-ISM and other peptide LAI programs in "
     "early development; mechanism compatible with peptide endocrine "
     "therapies. No commercial validation yet outside risperidone; "
     "commercial fit gated on Phase 3 demonstration."),

    ("ism", "oncology", "REFINE", 3, "medium",
     "Letrozole-ISM in Rovi's pipeline targets breast cancer hormonal "
     "therapy. Mechanism compatible with non-LHRH oncology hormonal LAI; "
     "incumbents (anastrozole, letrozole oral) and emerging SERDs compress "
     "commercial fit unless ISM offers structural advantage."),

    # REMOVE (speculative — rubric says "Omit indications where fit is irrelevant")
    ("chroniject", "psych", "REMOVE", None, None,
     "Removed: speculative — Oakwood has no disclosed commercial-stage "
     "psych program on Chroniject."),
    ("chroniject", "oncology", "REMOVE", None, None,
     "Removed: speculative — no oncology programs on Chroniject publicly "
     "disclosed."),
    ("maritide", "endocrine", "REMOVE", None, None,
     "Removed: speculative — Amgen MariTide focus is metabolic/obesity; no "
     "broader endocrine programs disclosed."),
    ("medusa", "endocrine", "REMOVE", None, None,
     "Removed: speculative — Adocia has no late-stage endocrine programs "
     "post-Lilly insulin partnership termination."),
    ("nanocrystal", "addiction", "REMOVE", None, None,
     "Removed: speculative — no NanoCrystal LAI advanced for OUD; "
     "Sublocade and Brixadi own that category."),
    ("nanocrystal", "oncology", "REMOVE", None, None,
     "Removed: speculative — no NanoCrystal LAI advanced for oncology."),
    ("nanozolid", "endocrine", "REMOVE", None, None,
     "Removed: speculative — LIDDS focus is intratumoral oncology and "
     "intra-articular; no endocrine programs disclosed."),
    ("spectrum", "endocrine", "REMOVE", None, None,
     "Removed: speculative — Foresee has no non-oncology endocrine "
     "programs publicly disclosed."),
]


def update_yaml(path: Path, mutations) -> bool:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return False
    changed = False
    for fn in mutations:
        if fn(data):
            changed = True
    if changed:
        path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
            encoding="utf-8",
        )
    return changed


def set_score(data: dict, score_path: str, value, confidence, rationale) -> bool:
    parts = score_path.split(".")
    parent = data
    for p in parts[:-1]:
        parent = parent.setdefault(p, {})
    leaf = parts[-1]
    existing = parent.get(leaf) or {}
    new_val = {
        "value": value,
        "rationale": rationale,
        "confidence": confidence,
        "scored_at": "2026-04-27",
        "scorer": "CL",
    }
    if existing.get("inherited_from"):
        new_val["inherited_from"] = existing["inherited_from"]
    parent[leaf] = new_val
    return True


def find_platform_file(platform_id: str) -> Path | None:
    """Match a platform id to its yaml file (filename may not always match id)."""
    direct = PLATFORMS / f"{platform_id}.yaml"
    if direct.exists():
        return direct
    for f in PLATFORMS.glob("*.yaml"):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8"))
            if d and d.get("id") == platform_id:
                return f
        except Exception:
            continue
    return None


def main():
    n_changed = 0

    # (A) Availability
    for pid, (value, conf, rationale) in AVAILABILITY.items():
        path = find_platform_file(pid)
        if path is None:
            print(f"  SKIP missing: {pid}", file=sys.stderr)
            continue
        if update_yaml(path, [
            lambda d, v=value, c=conf, r=rationale: set_score(
                d, "scores.availability", v, c, r),
        ]):
            print(f"  availability updated: {pid}")
            n_changed += 1

    # (B) Specific scores
    for entity_kind, file_id, score_path, value, conf, rationale in SPECIFIC_SCORES:
        if entity_kind == "platform":
            path = find_platform_file(file_id)
        else:
            path = ASSETS / f"{file_id}.yaml"
            if not path.exists():
                path = None
        if path is None:
            print(f"  SKIP missing: {entity_kind}/{file_id}", file=sys.stderr)
            continue
        if update_yaml(path, [
            lambda d, sp=score_path, v=value, c=conf, r=rationale: set_score(
                d, sp, v, c, r),
        ]):
            print(f"  {score_path} updated: {entity_kind}/{file_id}")
            n_changed += 1

    # (C) Indication fits
    for plat_id, ind, action, value, conf, rationale in INDICATION_FIT_UPDATES:
        path = find_platform_file(plat_id)
        if path is None:
            print(f"  SKIP missing: {plat_id}", file=sys.stderr)
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data is None:
            continue
        ind_fit = data.setdefault("indication_fit", {})
        if action == "REMOVE":
            if ind in ind_fit:
                del ind_fit[ind]
                path.write_text(
                    yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
                    encoding="utf-8",
                )
                print(f"  indication_fit.{ind} REMOVED from {plat_id}")
                n_changed += 1
        else:  # REFINE
            ind_fit[ind] = {
                "value": value,
                "rationale": rationale,
                "confidence": conf,
                "scored_at": "2026-04-27",
                "scorer": "CL",
            }
            path.write_text(
                yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
                encoding="utf-8",
            )
            print(f"  indication_fit.{ind} REFINED in {plat_id}")
            n_changed += 1

    print(f"\n{n_changed} score(s) updated.")


if __name__ == "__main__":
    main()
