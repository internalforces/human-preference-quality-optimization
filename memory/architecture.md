# Architecture Briefing

> Concise agent-oriented summary. For full detail, read `docs/architecture.md`.

## Pipeline at a Glance

```
ingest → features → queue → [human review] → validate → train-model → suggest
```

Each step reads from the previous step's output file and writes one output file:

| Step | Reads | Writes |
|------|-------|--------|
| ingest | StringArtio experiment folders | `data/processed/candidate_manifest.json` |
| features | `candidate_manifest.json` | `data/processed/features.csv` |
| queue | `features.csv`, `preferences.jsonl` | `data/review_queue/review_queue.jsonl` |
| train-model | `preferences.jsonl`, `features.csv` | `data/processed/preference_model.json` |
| suggest | `preference_model.json`, `features.csv` | `data/suggestions/suggested-configs.json` |

## Key Architectural Facts

- **Source-level candidates:** One experiment config rendered for N source images = N candidate rows, not 1.
- **Preference model:** Bradley-Terry-style pairwise logistic ranking. `tie` = weak equality loss. `both_bad` = failure signal, not a winner.
- **Fallback model:** If labels are missing or insufficient, a metric-fallback model is emitted. This is normal. Real HPL begins after human labels exist.
- **Review queue:** Same-source, blind. After a model exists, pairs uncertain candidates with low-failure anchors.
- **Optimizer:** Constrained BO. Consumes the generation-quality contract from StringArtio for runtime, line-count, and visibility floors. Writes suggestions only — does not execute generator runs.
- **Rendered SVG diagnostics:** Stroke opacity/width extracted from output SVG files. Used for visual risk scoring in queue generation and optimizer base selection. Not a human label.

## Boundary with StringArtio

- Read from: `/path/to/stringartio/experiments`
- Read contract from: StringArtio `docs/string-art/generation-quality-contract.json`
- Never write to the StringArtio repository
- Never execute `scripts/stringArtExperimentRunner.mjs`

## Source Layout

```
src/stringartio_preference_lab/
  cli.py          — entry point, command routing
  ingest.py       — artifact ingestion and manifest building
  features.py     — feature extraction and CSV export
  review_queue.py — active-learning queue generation
  preferences.py  — label validation and parsing
  model.py        — preference model training
  optimizer.py    — constrained BO suggestion generation
  schema.py       — shared data schemas
  config.py       — lab configuration loading
  generation_quality_contract.py — contract parsing and constraint application
  svg_diagnostics.py — rendered SVG diagnostic extraction
  utils.py        — shared utilities
```
