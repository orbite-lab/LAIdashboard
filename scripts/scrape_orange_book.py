#!/usr/bin/env python3
"""
scrape_orange_book.py — Pull Orange Book patent records for LAI assets and
emit data/ip/<slug>.yaml stubs.

Stays in LAI scope by filtering on a curated map of {NDA: asset_id} for
known long-acting injectable / depot / implant products.

The FDA distributes the Orange Book as a tilde-delimited ZIP. Default
download URL: https://www.fda.gov/media/76860/download (updated monthly).
Cached locally to db/orange_book.zip — re-runs are fast.

Usage:
    python scripts/scrape_orange_book.py
    python scripts/scrape_orange_book.py --refresh        # force re-download
    python scripts/scrape_orange_book.py --asset sublocade
    python scripts/scrape_orange_book.py --dry-run

Patent expiry beyond Orange Book "Patent_Expire_Date_Text" is not modeled
(no PTE/PTA — the Orange Book lists the headline expiry the holder asserts).
Records are marked "verify" in notes since holders sometimes overstate.
"""

import argparse
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IP_DIR = REPO / "data" / "ip"
CACHE_PATH = REPO / "db" / "orange_book.zip"
SOURCE_URL = "https://www.fda.gov/media/76860/download"

# {NDA_application_number: (asset_id, platform_id, sponsor_label)}
# All in-scope LAI / depot / implant products in the tracker.
NDA_TO_ASSET = {
    # Atrigel
    "209819": ("sublocade",        "atrigel",       "Indivior"),
    "021379": ("eligard",          "atrigel",       "Tolmar"),
    # FluidCrystal
    "213005": ("brixadi",          "fluidcrystal",  "Camurus / Braeburn"),
    # BEPO
    "217055": ("uzedy",            "bepo",          "MedinCell / Teva"),
    # Medisorb
    "021897": ("vivitrol",         "medisorb",      "Alkermes"),
    "021346": (None,               "medisorb",      "Janssen Risperdal Consta"),
    # NanoCrystal
    "022264": ("invega_sustenna",  "nanocrystal",   "Janssen"),
    "207946": (None,               "nanocrystal",   "Janssen Invega Trinza"),
    "215912": ("invega_hafyera",   "nanocrystal",   "Janssen"),
    "215499": ("apretude",         "nanocrystal",   "ViiV"),
    "212888": ("cabenuva",         "nanocrystal",   "ViiV / Janssen"),
    "212887": ("cabenuva",         "nanocrystal",   "ViiV / Janssen"),
    # Lupron Depot
    "020517": ("lupron_depot",     "lupron_depot_platform",  "AbbVie / Takeda"),
    # Trelstar
    "020715": (None,               "trelstar_platform", "Allergan / Watson"),
    # Zoladex
    "019726": (None,               "zoladex_implant",   "AstraZeneca"),
    # Sandostatin LAR
    "021008": ("sandostatin_lar",  "sandostatin_lar_platform", "Novartis"),
    # Somatuline
    "022074": ("somatuline_depot", "somatuline_autogel", "Ipsen"),
    # Signifor
    "203255": (None,               "signifor_lar_platform",  "Recordati / Novartis"),
    # DepoFoam
    "022496": ("exparel",          "depofoam",      "Pacira"),
    # Durasert / iDose / Novadur (ophthalmic implants)
    "201923": (None,               "durasert",      "Alimera Sciences (Iluvien)"),
    "210331": (None,               "durasert",      "EyePoint (Yutiq)"),
    "208912": (None,               "durasert",      "EyePoint (Dexycu)"),
    "211911": (None,               "novadur",       "AbbVie/Allergan (Durysta)"),
    "215025": (None,               "idose",         "Glaukos (iDose TR)"),
    # SpectruM (Foresee)
    "213796": (None,               "spectrum",      "Foresee / Accord (Camcevi)"),
    # Probuphine
    "204442": (None,               "probuphine",    "Titan / Braeburn"),
    # ISM (Rovi)
    "212849": (None,               "ism",           "Rovi (Risvan / Okedi US filing)"),
    # Perseris
    "210126": (None,               "perseris_platform", "Indivior (Perseris — discontinued)"),
}


def slugify(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:max_len]


def download(force: bool = False) -> Path:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_PATH.exists() and not force:
        # Reuse cache if recent
        age_days = (datetime.now() - datetime.fromtimestamp(CACHE_PATH.stat().st_mtime)).days
        if age_days < 14:
            print(f"  using cached {CACHE_PATH.name} ({age_days}d old)")
            return CACHE_PATH
    print(f"  downloading {SOURCE_URL} ...")
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(CACHE_PATH, "wb") as out:
        out.write(r.read())
    print(f"  saved {CACHE_PATH.name} ({CACHE_PATH.stat().st_size // 1024}KB)")
    return CACHE_PATH


def parse_zip(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (products, patents) records. Each is a dict keyed by column name."""
    products = []
    patents = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        prod_name = next((n for n in names if "products" in n.lower() and n.lower().endswith(".txt")), None)
        pat_name = next((n for n in names if "patent" in n.lower() and n.lower().endswith(".txt")), None)
        if not prod_name or not pat_name:
            raise RuntimeError(f"products/patent.txt not found in zip; got {names}")
        with zf.open(prod_name) as f:
            text = f.read().decode("latin-1")
            lines = text.splitlines()
            header = lines[0].split("~")
            for line in lines[1:]:
                parts = line.split("~")
                if len(parts) != len(header):
                    continue
                products.append(dict(zip(header, parts)))
        with zf.open(pat_name) as f:
            text = f.read().decode("latin-1")
            lines = text.splitlines()
            header = lines[0].split("~")
            for line in lines[1:]:
                parts = line.split("~")
                if len(parts) != len(header):
                    continue
                patents.append(dict(zip(header, parts)))
    return products, patents


def to_yaml(d: dict) -> str:
    out = []
    for k, v in d.items():
        if v is None:
            out.append(f"{k}: null")
        elif isinstance(v, list):
            if not v:
                out.append(f"{k}: []")
            else:
                out.append(f"{k}:")
                for item in v:
                    out.append(f"  - {json.dumps(item)}")
        elif isinstance(v, str) and ("\n" in v or len(v) > 100):
            out.append(f"{k}: >")
            for line in v.split("\n"):
                out.append(f"  {line}")
        elif isinstance(v, str):
            out.append(f"{k}: {json.dumps(v)}")
        else:
            out.append(f"{k}: {v}")
    return "\n".join(out) + "\n"


def parse_ob_date(text: str) -> str | None:
    """Orange Book stores dates as 'Mmm DD, YYYY' (e.g. 'May 19, 2031') or empty."""
    if not text or not text.strip():
        return None
    text = text.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text  # fall through — preserve raw text


def patent_to_yaml_record(pat: dict, asset_id: str | None,
                          platform_id: str, sponsor: str) -> tuple[str, dict]:
    appl = pat.get("Appl_No", "").strip()
    pat_no = pat.get("Patent_No", "").strip()
    expiry = parse_ob_date(pat.get("Patent_Expire_Date_Text", ""))
    submission_date = parse_ob_date(pat.get("Submission_Date", ""))
    use_code = pat.get("Patent_Use_Code", "").strip() or None
    drug_substance_flag = pat.get("Drug_Substance_Flag", "").strip().upper() == "Y"
    drug_product_flag = pat.get("Drug_Product_Flag", "").strip().upper() == "Y"
    pediatric = pat.get("Patent_Submission_Date", "").strip()  # non-standard, OB has variants

    # claim_type heuristic
    if drug_substance_flag and drug_product_flag:
        claim_type = "composition"
    elif drug_substance_flag:
        claim_type = "composition"
    elif drug_product_flag:
        claim_type = "formulation"
    elif use_code:
        claim_type = "use"
    else:
        claim_type = "formulation"

    base = asset_id or platform_id
    slug = slugify(f"ob_{base}_us_{pat_no}")

    notes_lines = [
        f"Auto-imported from Orange Book on {date.today().isoformat()}.",
        f"NDA: {appl}. Sponsor: {sponsor}.",
        "Expiry reflects FDA Orange Book listed date — does not include PTE/PTA",
        "or pediatric exclusivity. Verify against current Orange Book quarterly",
        "for ParaIV / IPR activity.",
    ]
    if use_code:
        notes_lines.append(f"Patent Use Code: {use_code} (method-of-use claim).")

    record = {
        "id": slug,
        "patent_number": f"US{pat_no}" if pat_no.isdigit() else pat_no,
        "jurisdiction": "US",
        "assignee": sponsor,
        "platform_id": platform_id,
        "asset_id": asset_id,
        "filing_date": None,
        "priority_date": None,
        "grant_date": None,
        "expiry_date": expiry,
        "claim_type": claim_type,
        "continuation_lineage": [],
        "paragraph_iv_filers": [],
        "ipr_petitions": [],
        "opposition_history": "Not assessed at import. Refresh against most recent OB and PTAB filings quarterly.",
        "notes": "\n".join(notes_lines),
        "source_urls": [
            f"https://www.accessdata.fda.gov/scripts/cder/ob/results_product.cfm?Appl_Type=N&Appl_No={appl}",
        ],
        "last_updated": date.today().isoformat(),
    }
    return slug, record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Force re-download of Orange Book")
    ap.add_argument("--asset", help="Restrict to a single asset_id (e.g. sublocade)")
    ap.add_argument("--platform", help="Restrict to a single platform_id (e.g. atrigel)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    IP_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = download(force=args.refresh)
    products, patents = parse_zip(zip_path)
    print(f"  parsed {len(products)} products, {len(patents)} patents")

    target_ndas = NDA_TO_ASSET
    if args.asset:
        target_ndas = {k: v for k, v in NDA_TO_ASSET.items() if v[0] == args.asset}
    if args.platform:
        target_ndas = {k: v for k, v in target_ndas.items() if v[1] == args.platform}
    if not target_ndas:
        print("No matching NDAs in NDA_TO_ASSET map.", file=sys.stderr)
        sys.exit(1)

    written = 0
    skipped = 0
    for pat in patents:
        appl = pat.get("Appl_No", "").strip()
        if appl not in target_ndas:
            continue
        asset_id, platform_id, sponsor = target_ndas[appl]
        try:
            slug, record = patent_to_yaml_record(pat, asset_id, platform_id, sponsor)
        except Exception as e:
            print(f"  ERROR formatting NDA{appl} patent {pat.get('Patent_No')}: {e}", file=sys.stderr)
            continue
        target = IP_DIR / f"{slug}.yaml"
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

    print(f"\n{written} written, {skipped} skipped (existing).")


if __name__ == "__main__":
    main()
