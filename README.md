# TactBio LAI Tracker

Unified research database for the long-acting injectable (LAI) biotech space. One foundation, three outputs: **Thesis Tracker**, **Deal Intelligence**, and **Platform Head-to-Head**.

## Philosophy

- **YAML is the source of truth.** All platforms, assets, deals, trials, and IP live as human-readable YAML files in `data/`. Git-versioned. Diff-friendly. No vendor lock-in.
- **SQLite is derived.** `scripts/build_db.py` compiles the YAML into a queryable SQLite database. Never edit the DB directly.
- **Scoring is a function, rubric is a document.** Python scoring logic in `scripts/score.py` must stay aligned with the written rubric in `docs/scoring_rubric.md`. If they drift, the rubric wins.
- **Outputs are regenerated, never hand-edited.** Markdown reports in `outputs/` are rebuilt from the DB. Edit the data, not the output.

## Workflow

```bash
# 1. Add or edit a data file (e.g. data/platforms/bepo.yaml)
# 2. Rebuild DB
python scripts/build_db.py

# 3. Regenerate outputs
python scripts/generate_outputs.py

# 4. Review outputs/*.md, then (optionally) convert to TactBio PDF via the skill
```

## Repo structure

```
tactbio-lai-tracker/
├── docs/                  # Methodology — taxonomy, rubrics, cadence
├── data/                  # Source of truth (YAML)
│   ├── platforms/         # Delivery platforms (BEPO, FluidCrystal, ...)
│   ├── assets/            # Drugs/products (UZEDY, Brixadi, ...)
│   ├── deals/             # Licensing, M&A, option structures
│   ├── trials/            # Clinical trial entries
│   └── ip/                # Patent positions
├── templates/             # Blank YAML templates for new entries
├── scripts/               # Ingestion, scoring, output generation
├── outputs/               # Auto-generated markdown reports
├── db/                    # SQLite (gitignored)
└── SKILL.md               # Claude skill trigger description
```

## Setup

```bash
pip install -r requirements.txt
python scripts/build_db.py        # builds db/lai.db from YAML
python scripts/validate.py        # checks YAML schema integrity
python scripts/generate_outputs.py
```

## Adding a new entry

1. Copy the appropriate template from `templates/` to the matching `data/` folder.
2. Rename it (lowercase, underscores: `my_platform.yaml`).
3. Fill it in. Required fields are documented in the template itself.
4. Run `scripts/validate.py`. Fix anything it flags.
5. Run `scripts/build_db.py` then `scripts/generate_outputs.py`.
6. Commit.

## Three outputs

| Output | Cadence | Audience | Source |
|---|---|---|---|
| `platform_h2h.md` | Annual refresh | Institutional (paid) | Platform + indication_fit scores |
| `thesis_tracker.md` | Quarterly | Institutional (paid) | Asset-level scores |
| `deal_pulse.md` | Monthly | Free teaser / paid full | Deals table, last 30 days |

## Scope discipline

v0 covers **injectable depot LAI only** (in-situ gel, microsphere, nanoparticle, implant, drug conjugate). Defer to v2: oral ultra-long-acting (Lyndra), half-life extended biologics, transdermal patches, long-acting GLP-1s (these get their own wedge if we take them).

## License

Proprietary — TactBio internal.
