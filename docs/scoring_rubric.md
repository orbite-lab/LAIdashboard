# Scoring Rubric — v0

This is the authoritative scoring methodology for the TactBio LAI tracker. Python scoring logic in `scripts/score.py` must stay aligned with this document. If they diverge, this document wins — update the code to match.

## General rules

- **Scale:** all scores are integers 1-5.
- **Rationale required:** every score entry must carry a one-sentence `rationale` string in the YAML.
- **Confidence required:** every score entry must carry `confidence` ∈ {high, medium, low}.
- **No orphan numbers.** A score without rationale and confidence is invalid and will be rejected by `scripts/validate.py`.
- **History tracked.** Every change to a score is logged in `scores_history` with timestamp and scorer initials. Score drift over 4+ quarters is product signal, not noise.

## Score meaning (generic)

| Score | Meaning |
|---|---|
| **5** | Best-in-class. Strong evidence across multiple dimensions. Genuine structural advantage. |
| **4** | Above average. Clear positive signal, some minor gaps or open questions. |
| **3** | Neutral/average. Works, but no structural advantage. Comparable to peer mean. |
| **2** | Below average. Material gaps or unresolved risks. |
| **1** | Weak. Broken on this dimension, or evidence strongly negative. |

If confidence is `low`, default toward 3 (neutral) unless there is a strong reason otherwise.

## Platform-level dimensions

### 1. Tech (`tech_score`)

Evaluates the platform's technical robustness as a delivery system.

**Inputs:**
- Release kinetics predictability (is in-vitro-in-vivo correlation established?)
- Payload breadth (small molecule only? peptides? proteins?)
- Duration range achievable (weeks? months? beyond?)
- CMC maturity (commercial-scale manufacturing established?)
- Injection site tolerability profile across programs

**Scoring anchors:**
- **5** — Multiple commercial products, demonstrated across ≥3 payload classes, industrial-scale CMC proven, tolerability well-characterized
- **4** — At least one commercial product, demonstrated across ≥2 payload classes, CMC scaled, minor tolerability questions
- **3** — One commercial product OR strong late-stage clinical validation, limited payload breadth
- **2** — Clinical stage only, payload class narrow, CMC uncertain
- **1** — Preclinical, speculative, or manufacturing failures on record

### 2. IP (`ip_score`)

Evaluates intellectual property strength and runway.

**Inputs:**
- Core composition-of-matter or method-of-use patent expiry dates
- Continuation strategy (layered continuations extending life cycle?)
- Freedom-to-operate concerns (competing claims, design-arounds?)
- Trade secret / know-how component (CMC lock-in difficult to replicate?)

**Scoring anchors:**
- **5** — Core patents to 2035+, multiple continuation layers, CMC trade secrets, no FTO concerns
- **4** — Core patents to 2030+, continuation pipeline in place, modest FTO exposure
- **3** — Core patents to 2028+, reasonable protection, some FTO questions or design-around risk
- **2** — Core patents expiring <2028, thin continuation strategy, FTO concerns
- **1** — Expired or expiring core IP, no continuation strategy, material FTO exposure

### 3. Dealability (`dealability_score`)

Evaluates the platform's demonstrated and prospective ability to command partnership economics.

**Inputs:**
- Quality of existing counterparties (Big Pharma vs. mid/small)
- Disclosed terms (upfront, milestones, royalties)
- Option structures (option-to-license, JV)
- Number of active programs / expansion track record
- Termination history (red flag if partners walk)

**Scoring anchors:**
- **5** — Multiple tier-1 pharma partners, disclosed royalties ≥ mid-single digits, clear option/expansion track record, no partner terminations
- **4** — At least one tier-1 pharma partner, competitive disclosed terms, one expansion or option exercise
- **3** — Mid-tier partners, terms undisclosed or market-rate, no major expansion yet
- **2** — Limited partnering, below-market disclosed terms, or failed partnerships
- **1** — No executed deals, or material partner terminations

## Asset-level dimensions

### 1. Tech (`tech_score`) — inherited

Asset tech score inherits the parent platform's tech score. Override requires rationale.

### 2. Clinical (`clinical_score`)

Evaluates clinical data quality and de-risking.

**Inputs:**
- Phase of development (higher phase = higher default)
- Data quality (primary endpoint met? effect size vs. SOC? statistical rigor?)
- Endpoint strength (regulatory-acceptable? patient-relevant?)
- Comparator choice (head-to-head vs. placebo vs. historical)
- Safety profile vs. existing treatments

**Scoring anchors:**
- **5** — Approved with strong label, real-world data confirmatory
- **4** — Phase 3 primary endpoint met with clinically meaningful effect, robust safety
- **3** — Phase 2 positive, Phase 3 designed or ongoing, reasonable safety
- **2** — Phase 1 data supportive but Phase 2 pending, or Phase 2 ambiguous
- **1** — Failed primary endpoint, or preclinical only

### 3. IP (`ip_score`)

Similar to platform IP but at asset level. Combines platform IP with asset-specific formulation/indication patents.

### 4. Dealability (`dealability_score`)

**Inputs:**
- Is the asset partnered? Terms?
- Partner commitment (have they continued to invest through milestones?)
- Geographic rights structure
- Termination risk (any notice given? performance clauses?)

### 5. Regulatory (`regulatory_score`)

**Inputs:**
- FDA/EMA interactions (Type B meetings, PIP, orphan, breakthrough designations)
- Regulatory precedent (is this pathway established or novel?)
- Post-marketing requirements if approved
- Label expansion feasibility

## Indication fit scoring (platform × indication matrix)

This is the heart of the **Platform H2H** output. For each (platform, indication) pair, score 1-5:

**Inputs:**
- Duration required by the indication (addiction needs ≥4 weeks; HIV PrEP wants ≥2 months; ophthalmology may want ≥6 months)
- Payload class fit (can the platform deliver the typical drug class for this indication?)
- Competitive set in that indication (is there already a dominant LAI?)
- Regulatory pathway clarity (is there a reference approval with this mechanism in this area?)
- Prescriber/site-of-care compatibility

**Scoring anchors:**
- **5** — Perfect fit: mechanism, duration, payload, and competitive landscape all favorable
- **4** — Good fit with one minor mismatch
- **3** — Workable fit but facing meaningful friction
- **2** — Significant mismatch on one dimension
- **1** — Fundamental mismatch — wouldn't pursue

## Confidence interpretation

- **high** — Multiple independent data points support this score. Would defend in writing.
- **medium** — Reasonable basis but gaps remain. Would caveat in writing.
- **low** — Placeholder based on limited public info. Flag for follow-up research.

Low-confidence scores with scores 4 or 5 should trigger review — claiming a strong score on thin evidence is a TactBio failure mode.

## Quarterly refresh checklist

For each scored entity at quarterly refresh:
1. Pull new clinical data since last refresh
2. Pull new deals or partner actions
3. Pull new IP filings (continuations, oppositions)
4. Re-read rationale — does it still hold?
5. If changing a score, write new rationale; old rationale stays in `scores_history`
6. If confidence should change, note why

## When to override inheritance

Asset tech score defaults to platform tech score. Override when:
- Asset-specific formulation substantially improves or weakens the platform baseline
- Real-world data contradicts platform-level characterization for this specific payload
- Asset-level manufacturing encounters issues not shared by other platform applications

Overrides require `rationale` explaining the delta.
