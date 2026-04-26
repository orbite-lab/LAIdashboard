# LAI Taxonomy — v1

This document defines what qualifies as a long-acting injectable (LAI) for TactBio tracker purposes, classifies platforms by mechanism, and documents the v1 schema fields that support the partner-scout and acquirer audiences.

**v1 changes from v0:** added `partnering_posture`, `encumbrances`, `technical_fit`, `cmc_capacity` blocks on platforms; added `data/companies/`; added `data/trials/` and `data/ip/` schemas; introduced audience-specific `views.{investor,partner,acquirer}` block.

## Scope

**In scope (v0):** parenteral (injected or implanted) formulations releasing drug over days, weeks, or months from a single administration.

**Out of scope (v0, defer to v2):**
- Oral ultra-long-acting formulations (Lyndra, gastric retention systems)
- Half-life extended biologics via Fc fusion, PEGylation, or albumin binding (these are not "depot" mechanisms)
- Transdermal patches (deliver continuously but route is different)
- Long-acting GLP-1 analogs released from the molecule itself (semaglutide, tirzepatide) — these are half-life engineered, not depot-formulated
- Controlled-release oral formulations
- Inhalation depots

**Edge cases:**
- **Implantable drug-eluting devices** (Durysta, Ozurdex, Yutrex, Vabysmo implants): IN scope. These are depots by any reasonable definition.
- **Microsphere IM formulations that also have oral versions** (Risperdal → Risperdal Consta): only the LAI version enters the tracker.
- **Combinations** (Cabenuva = rilpivirine LA + cabotegravir LA): tracked as a single combination asset referencing both LAI technologies.

## Classification by mechanism

Each platform is classified into exactly **one** primary mechanism. A platform using multiple mechanisms (rare) is classified by its lead commercial product.

| Code | Mechanism | Description | Examples |
|---|---|---|---|
| `in_situ_depot` | In-situ forming depot | Liquid injectate forms a solid/semi-solid depot on contact with aqueous body fluid or via polymer precipitation | Atrigel (Tolmar), BEPO (MedinCell), FluidCrystal (Camurus), ISM (Rovi) |
| `microsphere` | Microsphere suspension | Drug encapsulated in biodegradable polymer microspheres suspended for IM/SC injection | Medisorb (Alkermes/LinkeRx), PLGA-based microspheres (Oakwood Labs) |
| `nanoparticle` | Nanocrystal or nanosuspension | Drug formulated as nanoparticles for sustained dissolution | NanoCrystal (Alkermes — Invega Sustenna/Trinza) |
| `implant` | Solid implant | Pre-formed rod, wafer, or pellet inserted subcutaneously or intraocularly | Zoladex (AstraZeneca), Durysta (AbbVie/Allergan), PolyActiva implants |
| `drug_conjugate` | Drug-polymer conjugate | Drug covalently bound to a carrier releasing via hydrolysis | Medusa (Adocia), various PDC approaches |
| `liposome_depot` | Liposomal depot | Lipid-based slow-release depot (distinct from lipid nanoparticles for delivery) | Exparel (Pacira — bupivacaine liposomal) |
| `oil_solution` | Oil-based solution | Drug dissolved in oily vehicle for slow IM absorption (classical) | Decanoate esters (fluphenazine decanoate, haloperidol decanoate) |
| `peptide_self_assembly` | Peptide self-assembling depot | Peptide forms semi-solid gel matrix on injection (lanreotide-style) | Somatuline Autogel (Ipsen) |
| `other` | Other / novel | Any mechanism not covered above — must be described in platform YAML `mechanism_notes` | — |

## Classification by duration

Duration is the **label-indicated interval between injections** for the lead approved indication (or lead clinical indication if pre-approval).

- `short` — < 14 days
- `medium` — 14-60 days (typical monthly LAI)
- `long` — 60-180 days (bi-monthly to bi-yearly)
- `ultra_long` — > 180 days (6 months+)

## Classification by payload

- `small_molecule` — traditional small molecules (most LAI)
- `peptide` — peptides (GLP-1, GnRH analogs, octreotide)
- `protein` — proteins larger than peptides
- `biologic` — antibodies or antibody-like molecules (rare in true depot LAI)
- `nucleic_acid` — siRNA, ASO, mRNA (emerging)

## Classification by indication therapeutic area

Standardized ATA codes used across the tracker:

- `psych` — schizophrenia, bipolar, depression
- `addiction` — opioid use disorder, alcohol use disorder
- `hiv` — HIV treatment and PrEP
- `oncology` — all oncology
- `endocrine` — GnRH, octreotide, GLP-1, insulin
- `ophthalmology` — intraocular depots, periocular injections
- `pain` — post-surgical and chronic pain
- `cns_neuro` — non-psych CNS (migraine, epilepsy, etc.)
- `metabolic` — non-endocrine metabolic
- `other` — anything else (must be specified)

## v1 schema additions — partner-scout and acquirer fields

These fields support the BD-scouting and M&A audiences (see `outputs/partner_scout.md` and `outputs/target_screener.md`).

### `partnering_posture` (platform-level)

Stated and observed partnering openness.

```yaml
partnering_posture:
  open_to_partnering: true | false | selective
  open_indications: [list of indication codes]   # what's available to a new partner
  closed_indications: [list]                      # encumbered by exclusive deals
  open_geographies: [list of regions or "worldwide"]
  closed_geographies: [list]
  last_partnering_signal:
    date: 2025-06-03
    type: deal_announcement | jpm_presentation | bio_presentation | ir_inbound | none
    description: short string
  bd_contact_disclosed: true | false
```

### `encumbrances` (platform-level, auto-derivable from deals)

Indications, molecules, geographies locked by existing exclusive deals. `build_db.py` cross-references `data/deals/` to materialize this; manual overrides allowed.

```yaml
encumbrances:
  - deal_id: 2025_lilly_camurus_incretins
    indications: [metabolic, endocrine]
    molecule_classes: ["GIP/GLP-1", "GIP/glucagon/GLP-1", "amylin"]
    compound_count_locked: 4
    territory: worldwide
    exclusivity: exclusive
    expires: null            # date or "deal-life"
```

### `technical_fit` (platform-level)

Screenable attributes for pharma-scientist BD diligence.

```yaml
technical_fit:
  injection_volume_ml_range: [min, max]
  viscosity_cP_range: [min, max]
  needle_gauge_typical: "23G" | etc.
  max_payload_mass_mg: number or null
  cold_chain_required: true | false | partial
  excipient_classes: [list — PLGA, lipid, NMP, etc.]
  release_profile_summary: short string
  iv_ivc_established: true | false | partial
  injection_site: [SC | IM | intravitreal | intra-articular | implant | etc.]
```

### `cmc_capacity` (platform-level)

Manufacturing scale and headroom.

```yaml
cmc_capacity:
  primary_facility:
    location: city, country
    capacity_units_per_year: number or null
    units_definition: "doses" | "kg API" | etc.
  cdmo_partners: [list]
  capacity_headroom: ample | moderate | tight | unknown
  scale_up_timeline_months: number or null
  notes: short string
```

### `views` (platform / asset / deal level)

Audience-specific editorial. Legacy `tactbio_view` is preserved and treated as `views.investor` if `views` block is absent.

```yaml
views:
  investor: >
    Contrarian read, kill conditions, mispricing signal.
  partner: >
    Technical fit, posture, scale, available indications.
  acquirer: >
    Change-of-control, encumbrance map, integration cost, dilution.
```

### `data/trials/` schema

```yaml
id: trial_slug
nct_id: NCT-id-or-pending
asset_id: cross-reference
indication: indication_code
phase: 1 | 2 | 3 | 4
n: enrollment number
design: short string (RCT, single-arm, etc.)
primary_endpoint: short string
control_arm: SOC | placebo | active comparator | none
sponsor: company
status: planning | enrolling | active | completed | terminated | readout-pending
start_date: ISO date
expected_readout: ISO date or quarter
result: null | "positive" | "negative" | "mixed"
source_urls: [list]
last_updated: ISO date
```

### `data/ip/` schema

```yaml
id: patent_slug
patent_number: e.g. WO2010/119076 or US10,123,456
jurisdiction: WO | US | EP | JP | CN | etc.
assignee: company name
platform_id: cross-reference (or null)
asset_id: cross-reference (or null)
filing_date: ISO date
grant_date: ISO date or null
expiry_date: ISO date
claim_type: composition | method | formulation | device | use
continuation_lineage: [parent patent slugs]
paragraph_iv_filers: [list, if any]
ipr_petitions: [list with petitioner + status]
opposition_history: short string
notes: short string
source_urls: [list]
last_updated: ISO date
```

### `data/companies/` schema

```yaml
id: company_slug
name: full company name
ticker: stock ticker or null
listing_venue: NASDAQ | NYSE | Stockholm | Euronext Paris | etc.
country_hq: ISO code
employees: number or range
market_cap_usd_m: number or null
market_cap_as_of: ISO date
cash_position_usd_m: number or null
cash_runway_quarters: number or null
debt_usd_m: number or null
ifrs_or_gaap: IFRS | GAAP
key_insiders:
  - name: person
    role: role
    holding_pct: percentage or null
governance_notes: short string
m_and_a_protections:
  poison_pill: true | false | unknown
  staggered_board: true | false | unknown
  notes: short string
related_platforms: [platform slugs]
related_assets: [asset slugs]
related_deals: [deal slugs]
ir_contact: email or url
last_updated: ISO date
```

## v2 deferred items (do not add to v0 or v1)

Items the team has explicitly decided to track in a future version:

- Lyndra gastric retention oral platform
- Rezolute and others in glucose-responsive insulin depots
- Half-life extended biologics (Fc fusion, PEGylation, albumin binding)
- Transdermal patches (Zelsuvmi, Corplex, etc.)
- GI Dynamics and implanted-sleeve approaches

When the team decides to expand scope, update this file first, then the templates.
