#!/usr/bin/env python3
"""
refine_encumbrances.py — Replace [undisclosed] placeholder molecule_classes
on platform encumbrances with the actual molecule(s) where the deal scope
is publicly known.

Looks up each platform's encumbrance entries by deal_id and applies the
mapping in DEAL_MOLECULE_SCOPE. Only updates entries currently set to
['undisclosed'] — manually-set values are preserved.
"""

import sys
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parent.parent
PLATFORMS = REPO / "data" / "platforms"

# deal_id -> (molecule_classes, compound_count_locked)
DEAL_MOLECULE_SCOPE = {
    "2008_alimera_eyepoint_iluvien": (
        ["fluocinolone acetonide"], 1,
    ),
    "2014_az_alkermes_bydureon": (
        ["exenatide"], 1,
    ),
    "2016_viiv_janssen_cabenuva": (
        ["rilpivirine"], 1,  # the Janssen-side encumbrance covers RPV
    ),
    "2019_accord_foresee_camcevi": (
        ["leuprolide mesylate"], 1,
    ),
    "2019_recordati_novartis_signifor": (
        ["pasireotide"], 1,
    ),
    "2021_intas_foresee_camcevi": (
        ["leuprolide mesylate"], 1,
    ),
    "2023_royaltypharma_teva_olanzapine": (
        ["olanzapine"], 1,
    ),
    # Pre-existing more-specific entries on FluidCrystal and BEPO are
    # already correct and should not be touched (the loop checks for
    # ['undisclosed'] only).
}


def main():
    n_changed = 0
    for path in sorted(PLATFORMS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data is None:
            continue
        encs = data.get("encumbrances") or []
        changed = False
        for enc in encs:
            deal_id = enc.get("deal_id")
            mc = enc.get("molecule_classes")
            if not deal_id or not mc:
                continue
            if mc == ["undisclosed"] and deal_id in DEAL_MOLECULE_SCOPE:
                molecule_classes, compound_count = DEAL_MOLECULE_SCOPE[deal_id]
                enc["molecule_classes"] = molecule_classes
                if not enc.get("compound_count_locked"):
                    enc["compound_count_locked"] = compound_count
                changed = True
        if changed:
            path.write_text(
                yaml.dump(data, sort_keys=False, allow_unicode=True, width=88),
                encoding="utf-8",
            )
            print(f"  refined: {path.name}")
            n_changed += 1
    print(f"\n{n_changed} platform(s) refined.")


if __name__ == "__main__":
    main()
