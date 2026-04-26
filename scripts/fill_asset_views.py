#!/usr/bin/env python3
"""
fill_asset_views.py — Populate audience-specific views (investor / partner /
acquirer) on legacy approved assets that currently only carry tactbio_view.

The 16 legacy approved assets pre-date the v1 schema split. This script adds
hand-curated short paragraphs for each audience based on what is publicly
known about the asset's commercial position, ownership, and partnering
status. It is idempotent: only writes views.X if absent.

Editorial discipline — kept short and concrete. Each audience view is
2-4 sentences max, surfaces the most actionable information for that
audience, and avoids restating facts already in tactbio_view.
"""

import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "data" / "assets"

# asset_id -> {investor, partner, acquirer}
# investor view defaults to existing tactbio_view via the migration helper —
# only override here if the existing view doesn't lead with the contrarian /
# kill-condition framing that investor consumers want.
ASSET_VIEWS = {
    "uzedy": {
        "partner": (
            "Not available — Teva exclusive in psych under the 2013 BEPO master "
            "agreement. UZEDY's commercial trajectory is the principal "
            "real-world validation of BEPO platform manufacturing and "
            "regulatory execution; reference data point for any BD scout "
            "evaluating BEPO for non-psych indications."
        ),
        "acquirer": (
            "Asset cash flows are split between Teva (commercial gross profit) "
            "and MedinCell (mid-to-high single-digit royalties + commercial "
            "milestones). MedinCell acquirer thesis hinges on this royalty "
            "stream durability plus TEV-749 olanzapine PDUFA optionality. "
            "Diligence the 2013 Teva agreement for change-of-control terms."
        ),
    },
    "buvidal": {
        "partner": (
            "Camurus retains direct commercialization across EU and Australia. "
            "Closed for partnering on the buprenorphine-for-OUD scope. For BD "
            "scouts looking at FluidCrystal in addiction more broadly, the "
            "addiction encumbrance is locked through Braeburn (US) and "
            "Camurus-direct (ROW)."
        ),
        "acquirer": (
            "Camurus' largest direct-commercial revenue line. Acquirer thesis "
            "on Camurus rests on Buvidal franchise durability vs Sublocade "
            "EU expansion plus pipeline optionality (CAM2029, Lilly milestone "
            "tail). Verify Buvidal national reimbursement terms market-by-"
            "market — UK NHS, Nordic systems, Australia PBS each carry "
            "different access and pricing dynamics."
        ),
    },
    "brixadi": {
        "partner": (
            "US territory locked under Braeburn license (mid-teen royalties to "
            "Camurus). Not available for partnering. Reference deal economics "
            "(Camurus 13-17% royalty, $20M upfront 2014) inform what "
            "specialty-pharma counterparties will pay for FluidCrystal "
            "addiction scope."
        ),
        "acquirer": (
            "Brixadi US royalty stream (~SEK 212M / USD 20M FY2024) is a "
            "secondary contributor to Camurus enterprise value behind "
            "Buvidal. Braeburn change-of-control rights likely apply on a "
            "Camurus acquisition — verify the 2014 license and 2018 "
            "amendment provisions before structuring any deal."
        ),
    },
    "cabenuva": {
        "partner": (
            "Internal ViiV/Janssen co-development — closed. Reference for "
            "what HIV LAI co-development structures look like at tier-1 "
            "scale. BD scouts in HIV LAI must clear cabotegravir + rilpivirine "
            "exclusivity which extends through Janssen RPV-LA patent estate "
            "to ~2030+."
        ),
        "acquirer": (
            "Not actionable as a standalone target — ViiV is GSK-controlled "
            "(majority) with Pfizer (11.7%) and Shionogi (10%) minority "
            "consent rights. Any Cabenuva-related M&A would have to go "
            "through GSK and clear minority partners."
        ),
    },
    "apretude": {
        "partner": (
            "Internal ViiV asset — closed. Tracked encumbrance: Cabenuva-"
            "rilpivirine deal (2016) covers RPV component, separately ViiV "
            "owns CAB-LA. HIV PrEP LAI category limited to ViiV plus "
            "lenacapavir (Gilead) for foreseeable future."
        ),
        "acquirer": (
            "ViiV consolidation rumors recur periodically (full GSK rollup "
            "vs minority buyout); verify current GSK pharmaceutical strategy "
            "messaging. Apretude commercial trajectory is the leading "
            "indicator for whether HIV PrEP LAI achieves meaningful share "
            "of total PrEP spend."
        ),
    },
    "vivitrol": {
        "partner": (
            "Internal Alkermes asset on the Medisorb microsphere platform. "
            "Naltrexone is off-patent; commercial moat resides in "
            "manufacturing scale and prescriber relationships. Not "
            "externally licensable."
        ),
        "acquirer": (
            "Alkermes is a mid-cap with multiple commercial assets; Vivitrol "
            "is a meaningful contributor but not a dominant one. Acquirer "
            "thesis would key off Aristada + Vivitrol franchise economics "
            "plus residual NanoCrystal royalty streams."
        ),
    },
    "sublocade": {
        "partner": (
            "Indivior-internal — closed. Sublocade differentiates from "
            "Brixadi on monthly-only dosing and SC abdominal site; commercial "
            "lead in US OUD LAI. BD scouts comparing addiction LAI economics "
            "should benchmark against Sublocade's 2021-onwards revenue "
            "trajectory."
        ),
        "acquirer": (
            "Indivior corporate overhead (litigation history, governance, "
            "Reckitt spinoff legacy) complicates any acquirer thesis. "
            "Sublocade is the dominant value driver but enterprise risk "
            "is concentrated in single-product / single-indication exposure "
            "to OUD. Generic ANDA challenges to Sublocade IP create event "
            "risk."
        ),
    },
    "eligard": {
        "partner": (
            "Tolmar-private; not actively externally licensing. Atrigel core "
            "IP expired 2008; commercial value in manufacturing scale and "
            "regulatory history. New leuprolide LAI entrants must clear "
            "this incumbent's prescriber inertia."
        ),
        "acquirer": (
            "Tolmar is PE-owned (Carlyle) and has been a periodic M&A "
            "speculation target — verify current ownership against latest "
            "S&P Capital IQ. Eligard franchise plus the residual Sublocade "
            "contract revenue plus Atrigel platform IP / know-how represent "
            "the acquisition surface."
        ),
    },
    "exparel": {
        "partner": (
            "Pacira-internal. DepoFoam liposomal mechanism niche-bound to "
            "local administration — limited transferability beyond regional "
            "anesthesia. Not a credible LAI platform target outside the "
            "Pacira context."
        ),
        "acquirer": (
            "Pacira faces structural headwinds (generic ANDA challenges, "
            "payer pressure, opioid-sparing protocol shifts). Distressed-"
            "acquisition optionality grows as commercial trajectory "
            "deteriorates. Strategic acquirer would integrate DepoFoam "
            "into broader pain franchise plus evaluate Zilretta intra-"
            "articular extension."
        ),
    },
    "invega_sustenna": {
        "partner": (
            "Janssen-internal — closed. NanoCrystal IP estate remains "
            "Janssen-controlled (originally licensed from Alkermes/Elan). "
            "Reference asset for monthly LAI antipsychotic commercial "
            "economics ($4.5B FY2024 globally)."
        ),
        "acquirer": (
            "Not actionable — Janssen is wholly within J&J. Sustenna LOE "
            "trajectory is the central event for the schizophrenia LAI "
            "category over the next 5 years; Hafyera 6-monthly defends "
            "the franchise tier."
        ),
    },
    "invega_hafyera": {
        "partner": (
            "Janssen-internal — closed. 6-monthly duration is the "
            "highest-frequency-tier defensive moat in the Invega franchise."
        ),
        "acquirer": (
            "Not actionable — internal J&J asset. Hafyera commercial uptake "
            "rate is the empirical test for whether long-duration LAI "
            "commands sufficient premium to defend franchise economics; "
            "informs valuation read for any new ultra-long-duration LAI "
            "(e.g. CAM2029 6-monthly target)."
        ),
    },
    "lupron_depot": {
        "partner": (
            "AbbVie/Takeda-internal — closed. Off-patent reference product "
            "for prostate cancer LHRH LAI. Generic and innovator competition "
            "(Eligard, Camcevi, Trelstar) active in the category."
        ),
        "acquirer": (
            "Not actionable as a standalone target — embedded in AbbVie "
            "and Takeda commercial portfolios. Strategic relevance is as "
            "the price/share anchor for any new LHRH LAI entrant."
        ),
    },
    "risperdal_consta": {
        "partner": (
            "Janssen-internal. Off-patent in major markets; generic "
            "risperidone microsphere products available in some "
            "territories. Closed for partnering; tracked as historical "
            "context."
        ),
        "acquirer": (
            "Not actionable — Janssen-internal mature asset. Strategic "
            "relevance is as a cannibalization-precedent — Sustenna "
            "displaced Consta in J&J's portfolio; informs read on how "
            "later-generation LAIs (Hafyera, UZEDY, TEV-749) reshape "
            "category dynamics."
        ),
    },
    "sandostatin_lar": {
        "partner": (
            "Novartis-internal. Off-patent peptide LAI; manufacturing scale "
            "and prescriber relationships are the residual moat. New "
            "octreotide LAI entrants (CAM2029) directly target this "
            "franchise."
        ),
        "acquirer": (
            "Novartis has divested mature peptide LAI franchises before "
            "(2019 Recordati Signifor deal). Sandostatin LAR carve-out "
            "remains a periodic strategic question; valuation would "
            "follow generic-pressure-adjusted economics."
        ),
    },
    "somatuline_depot": {
        "partner": (
            "Ipsen-internal. Self-assembling peptide LAI mechanism is "
            "uniquely Ipsen's; not externally licensable. New lanreotide "
            "LAI entrants would need to design around the self-assembly "
            "mechanism."
        ),
        "acquirer": (
            "Ipsen is a specialty pharma with founder-family majority "
            "control — restricts hostile M&A. Somatuline IP cliff is the "
            "central question for franchise valuation; defense via new "
            "indications or generic-restricted geographies informs the "
            "trajectory."
        ),
    },
    "susvimo": {
        "partner": (
            "Roche/Genentech-internal — closed. PDS device technology is "
            "proprietary and uniquely manufactured. Reference precedent "
            "for biologic LAI device-formulation hybrids."
        ),
        "acquirer": (
            "Not actionable — Roche-controlled (founder family voting "
            "block). Susvimo recall-and-relaunch trajectory is the "
            "cautionary case study for any acquirer evaluating device-"
            "formulation hybrid LAI assets."
        ),
    },
}


def main():
    n_changed = 0
    for asset_id, views in ASSET_VIEWS.items():
        path = ASSETS / f"{asset_id}.yaml"
        if not path.exists():
            print(f"  SKIP missing: {asset_id}", file=sys.stderr)
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data is None:
            continue
        existing = data.setdefault("views", {})

        # Investor view defaults to existing tactbio_view if not set
        if "investor" not in existing and data.get("tactbio_view"):
            existing["investor"] = data["tactbio_view"]
        for audience, text in views.items():
            if audience not in existing or existing[audience] is None:
                existing[audience] = text

        path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
            encoding="utf-8",
        )
        print(f"  updated: {path.name}")
        n_changed += 1
    print(f"\n{n_changed} asset(s) updated.")


if __name__ == "__main__":
    main()
