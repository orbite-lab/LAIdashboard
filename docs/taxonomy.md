# LAI Taxonomy — v0

This document defines what qualifies as a long-acting injectable (LAI) for TactBio tracker purposes, and how platforms are classified by mechanism.

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

## v2 deferred items (do not add to v0)

Items the team has explicitly decided to track in a future version:

- Lyndra gastric retention oral platform
- Rezolute and others in glucose-responsive insulin depots
- Half-life extended biologics (Fc fusion, PEGylation, albumin binding)
- Transdermal patches (Zelsuvmi, Corplex, etc.)
- GI Dynamics and implanted-sleeve approaches

When the team decides to expand scope, update this file first, then the templates.
