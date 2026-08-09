# Data Flow

This file describes the operational pipeline for the sidecar HPL workflow.
For repository boundaries, see [Architecture](architecture.md). For label
format details, see [Preference Schema](preference-schema.md). For agent rules,
see [Agent Instructions](../AGENTS.md). For faint app-upload candidates, see
[Visibility Failure Analysis](visibility-failure-analysis.md).

0. `source-suite` (optional robustness setup)
   - Downloads a fixed open-license photo suite into
     `data/source_suite/robustness/images`.
   - Writes `manifest.json` with category, source URL, license, attribution,
     local path, dimensions, and SHA-256 for each photo.
   - Writes a StringArtio-compatible `dataset.json` template that points source
     and target to the same local image for manual generator experiments.
   - Does not run StringArtio experiments automatically.

0a. `validate-robustness-dataset` (optional runner-ready dataset check)
   - Reads the StringArtio app repo dataset at
     `experiments/rl-training/robustness/dataset.json` by default.
   - Checks that `pair-1` through `pair-9` exist, that `pair-2` and `pair-4`
     are available for existing proxy presets, and that all source/target
     images are 1000x1000.
   - Does not run StringArtio experiments automatically.
   - After a human starts a StringArtio run and artifacts exist, normal
     `ingest` reads those results for HPL.

1. `ingest`
   - Reads StringArtio experiment folders.
   - Loads StringArtio's generation-quality contract and uses it for app-ready
     heuristics such as runtime, line count, max pins, allowed modes, and
     forbidden target-aware config fields.
   - Normalizes result episodes, artwork summaries, best configs, and promotion
     previews.
   - Stores `runtime_ms` at source-level artifact granularity, dividing batch
     `totalMs` by artifact count for multi-source or repeated episodes.
   - Reads existing output SVG artifacts and stores rendered stroke diagnostics
     under `metadata.rendered_svg`, including stroke opacity/width summaries,
     rendered line count, and SVG warning counts.
   - Writes `data/processed/candidate_manifest.json`.

2. `features`
   - Flattens numeric metrics and config values.
   - Adds a derived visible-ink score from `lineInk`,
     `visualOpacityScale`, and `visualWidthScale` when all three are present.
   - Exports rendered SVG diagnostic columns such as
     `rendered_svg_stroke_opacity_mean` and
     `rendered_svg_stroke_width_mean`.
   - Exports residual diagnostic metrics when future StringArtio artifacts emit
     them, including `residualLumaScore`, `residualRgbScore`,
     `renderedResidualLumaScore`, and `renderedResidualRgbScore`.
   - Writes `data/processed/features.csv`.

3. `queue`
   - Groups candidates by `source_id`.
   - Skips already labeled pairs.
   - Prioritizes uncertain and randomly explored pairs while mixing in
     app-ready, low-failure anchor candidates when a trained model exists.
   - Interleaves selected rows by `source_id` so review batches do not overfit
     the model toward one source image.
   - Adds rendered SVG opacity/width diagnostics to visual-risk scoring when
     those diagnostics are present.
   - Penalizes pairings where both candidates look failure-prone, reducing
     `both_bad`-vs-`both_bad` review loops.
   - Writes `data/review_queue/review_queue.jsonl`.

4. Human review
   - Review `blind_artifacts` first.
   - Use `diagnostic_artifacts` after making the blind choice.
   - Append labels to `data/preferences/preferences.jsonl`.

5. `train-model`
   - Validates labels against the manifest.
   - Trains a pairwise preference model or emits a graceful fallback.
   - Uses `better_visibility` reason flags as lower-weight auxiliary signals
     over rendered visibility, visible-ink, and contrast columns.
   - Excludes residual diagnostic metrics from model features by default until
     an ablation shows that they improve agreement with human labels.
   - Writes `data/processed/preference_model.json`.

6. `suggest`
   - Uses constrained preference-guided perturb-and-rank search, not GP-based
     Bayesian Optimization.
   - Loads StringArtio's generation-quality contract and writes its
     version/hash/source into `constraints.generation_quality_contract`.
   - Filters to app-ready, runtime-safe, line-count-safe, visibility-safe
     candidates using the contract's minimum visibility floors.
   - Interleaves stable base anchors by `source_id` before reusing additional
     anchors from the same source image.
   - Raises emitted suggestions to the contract's app-upload visibility target
     instead of leaving them near the minimum floor.
   - Steers emitted line counts toward the contract's preferred moderate-density
     band while preserving the hard line-count limit.
   - Prefers stable base candidates with no observed `both_bad` signal before
     reusing failure-observed candidates.
   - Penalizes faint or malformed rendered SVG diagnostics in base-candidate
     risk scoring without turning those diagnostics into human labels.
   - Includes base visible-ink and rendered SVG statistics in suggestion
     provenance when available.
   - Marks suggestion packets with a default `preference_tuning_suggestion`
     intent and supported handoff intents for render/model calibration, bounded
     add/remove local search, and conservative auto-color experiments.
   - Removes target-aware logic.
   - Writes `data/suggestions/suggested-configs.json`.

7. `evaluate`
   - Recomputes actual label counts, constraint pass rates, runtime summaries,
     source/run holdouts, and baseline/ablation results.
   - Fits normalization and model weights from training groups only.

8. `review`
   - Serves the tracked blind-review UI from the installed package.
   - Writes append-only preferences with interface and queue provenance.

If the contract cannot be read, Lab preserves current fallback behavior and
records a warning so the suggestion file is not mistaken for a contract-matched
handoff.

## Reusable Review Browser Format

Ad hoc HPL passes may include a static browser review file next to the source
queue, for example `data/review_queue/<batch>-blind-review.html`. The JSONL
queue remains the source of truth; the HTML is a reviewer-facing shell for blind
A/B choices, reason capture, and export.

The source queue used by a static review browser should keep one JSON object per
pair with these fields:

- `queue_id`: stable row id used for DOM ids, persisted browser state, and
  exported `preference_id` suffixes.
- `source_id`: shared source image id. Candidate A and B must have the same
  `source_id`.
- `candidate_a` and `candidate_b`: manifest candidate ids. They must be
  different candidates.
- `blind_artifacts`: object with `A` and `B` paths, shown before diagnostics.
- `diagnostic_artifacts`: object with `A` and `B` paths, hidden in a collapsed
  details section until after the blind choice.
- `priority`, `review_index`, `batch_id`, `created_at`, and
  `selection_reasons`: optional reviewer context and provenance.

The static HTML format should keep this layout:

- Reviewer-facing labels, helper text, placeholders, and diagnostics summaries
  should be Korean-friendly. Preserve machine-readable schema keys and values
  in exported JSONL.
- Toolbar with selected count, `JSONL 내보내기`, and `선택 초기화`.
- One `section.review-card` per queue row, with `data-queue-id` set to the
  queue row id.
- A card header showing review index, source id, priority, and brief purpose
  when available.
- A two-column blind comparison area labeled A and B using `blind_artifacts`.
- Winner controls inside the card with exactly these choices: `A`, `B`, `tie`,
  and `both_bad`.
- Reason checkboxes using only the schema-defined `reason_flags` values, while
  their visible labels may be Korean, plus an optional per-card notes textarea
  for the reviewer's selection rationale.
- A collapsed diagnostics area labeled in Korean, using `diagnostic_artifacts`
  and numeric provenance from `selection_reasons`.
- Browser `localStorage` persistence scoped by batch/file so accidental reloads
  do not lose in-progress review choices.

`Export JSONL` should emit one appendable preference record per selected card.
Each record must include `preference_id`, `source_id`, `candidate_a`,
`candidate_b`, `winner`, `reviewer`, `timestamp`, `reason_flags`, and `notes`.
The browser must not write directly to `data/preferences/preferences.jsonl`;
the reviewer should append exported records deliberately and then run
`validate-preferences`.

The browser is allowed to display metrics and selection provenance, but those
values are diagnostic only. They must not be treated as human labels, and they
must not replace the reviewer's blind choice.
