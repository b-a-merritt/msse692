---
name: hevner-dsr
description: Drive a design science research (DSR) idea from conception to publication using Hevner's seven guidelines as quality gates. Use for any DSR or research-paper work — scoping or stress-testing an idea, checking problem relevance, planning or reviewing an evaluation, framing the contribution, structuring or auditing the manuscript, or picking a venue. Triggers include DSR, design science, Hevner, artifact, evaluation plan, research contribution, manuscript, submission, venue.
argument-hint: "[idea | question | path to draft]"
---

# Hevner DSR — Conception to Publication

Source: Hevner, March, Park & Ram (2004), MIS Quarterly 28(1). Treat the seven guidelines as pass/fail gates, not decoration. Every output BLUF: verdict → gaps → fixes.

## Procedure

1. **Locate** — map whatever the user provides (idea, draft, results, question) to the earliest pipeline stage with an unmet gate.
2. **Audit** — score all seven gates pass / weak / missing against current materials; report as a scorecard, one line per gate.
3. **Advance** — fix the earliest failing gate and state exactly what evidence flips it to pass. Never polish later stages while an earlier gate fails.

## The seven gates

| G | Guideline | Pass when |
|---|-----------|-----------|
| 1 | Design as an artifact | A named construct, model, method, or instantiation is specified precisely enough to build and apply |
| 2 | Problem relevance | Specific stakeholders and an evidenced, unsolved problem they care about |
| 3 | Design evaluation | Utility, quality, or efficacy demonstrated by an appropriate method with defined metrics |
| 4 | Research contributions | Verifiable delta over prior art: artifact, design foundations, or design methodology |
| 5 | Research rigor | Defensible methods in both construction and evaluation; grounded in the knowledge base; limitations stated |
| 6 | Design as a search process | Alternatives generated and rejected for stated reasons; iterations documented; satisficing justified |
| 7 | Communication of research | Legible to technical and managerial readers; artifact reproducible from the text |

## Pipeline

**S0 — Conception.** Force three answers: artifact type (G1)? Whose problem, with evidence it is real and unsolved (G2)? What "works" means, measurably (G3 seed)? Kill test: a known solution to a known problem is routine design, not research — reshape or drop.

**S1 — Knowledge base.** Targeted lit review: prior artifacts (defines the G4 delta) and kernel theories / justificatory knowledge (G5). Output: the gap in one sentence.

**S2 — Design & build (G1, G6).** Specify, then build the artifact. Log every design alternative and why it lost — that log is the G6 evidence and becomes the paper's design rationale.

**S3 — Evaluation (G3, G5).** Method must match artifact and claim strength: observational (case study, field study) · analytical (static, architecture, optimization, dynamic analysis) · experimental (controlled experiment, simulation) · testing (functional, structural) · descriptive (informed argument, scenarios — weakest; caps the venue tier, say so if chosen). Define metrics and threats to validity before running anything.

**S4 — Contribution (G4).** Classify per Gregor & Hevner (2013): improvement (new solution, known problem) · exaptation (known solution, new problem) · invention (new, new). State the contribution as one falsifiable sentence.

**S5 — Manuscript (G7).** Gregor–Hevner publication schema, in order: Introduction (problem, significance, RQ) · Literature review · Method (declare the DSR process followed, e.g. Peffers et al. DSRM) · Artifact description · Evaluation · Discussion (contributions, limitations, implications) · Conclusions. Abstract last: problem → artifact → evaluation result → contribution, four sentences.

**S6 — Venue & submission.** Fit = scope match + indexing + timeline. Project defaults: WoS-indexed, ≤12 months to publication, APCs acceptable. Verify the venue has published DSR recently; if not, expect a methods fight in review. Before submitting, rerun the full gate audit on the manuscript — every gate must point to the section that evidences it.

## Rules

- A G2 failure is fatal: no relevance, no paper. Say so early.
- G3 is where DSR papers die in review; evaluation strength must match claim strength.
- One artifact, one claim, one contribution sentence — sprawl kills acceptance.
- All outputs BLUF: claim, evidence, implication. No throat-clearing, no hedging filler.
