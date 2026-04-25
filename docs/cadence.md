# Cadence — Workflow & Publication Schedule

## Daily (15 min)

- **Deal alert triage.** Check Google Alerts for LAI partnership language, SEC 8-K feeds for companies on the watchlist. Flag anything relevant; no YAML edits required unless something genuinely new.
- **Trial readout calendar.** Glance at upcoming trial readouts (tracked in `data/trials/`). Flag anything within 2 weeks.

## Weekly (2 hours)

- **Score review.** Any new data since last week that warrants a score change? Edit YAML, `build_db.py`, commit.
- **Deal DB updates.** Any confirmed deal from the week? Add to `data/deals/`.
- **Validation run.** `python scripts/validate.py` — fix anything flagged.

## Monthly (1 day)

- **Deal pulse publication.** `python scripts/generate_outputs.py` — review `outputs/deal_pulse.md`. Write the editorial framing (top 3 takeaways, signal vs. noise). Publish.
- **Trial readout summary.** Any readouts this month that moved a thesis? Document in the next quarterly.

## Quarterly (1 week, split across 2 people)

- **Full scoring refresh** per the checklist in `docs/scoring_rubric.md`.
- **Thesis tracker publication.** Review `outputs/thesis_tracker.md`, write editorial framing, PDF via TactBio skill.
- **"State of Long-Acting" letter.** Free, public-facing. Synthesizes the quarterly's key themes. Top-of-funnel marketing.

## Annually (2 weeks)

- **Platform H2H refresh.** All platform × indication cells re-scored. `outputs/platform_h2h.md` regenerated. Flagship annual release.
- **Taxonomy review.** Any new modalities that should enter scope? Any v2 items ready for promotion?
- **Rubric review.** Did any scoring anchor prove miscalibrated this year? Update and document in a changelog.

## Ad-hoc

- **Triggered deep dives.** A significant catalyst on a tracked name triggers a standalone memo via the TactBio PDF skill. Data inputs come from this tracker; output is a one-off PDF, not a periodic.

## Responsibilities

- **Romain:** editorial voice, thesis framing, score overrides, partner dialogue inputs
- **Christophe:** data ingestion, scoring hygiene, YAML integrity, publication pipeline
- **Shared:** quarterly refresh, annual H2H, rubric calibration

## Time budget guardrail

Total tracker-maintenance time (ex-publication) should not exceed **25% of weekly hours**. If it does, the tracker is consuming what should be memo output. Cut scope before cutting quality.
