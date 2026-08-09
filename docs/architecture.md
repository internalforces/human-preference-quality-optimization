# Architecture

StringArtio Preference Lab is a sidecar HPL pipeline. The app remains the
runtime and candidate generator; this repository reads artifacts and produces
research outputs beside them.

For command-level flow, see [Data Flow](data-flow.md). For human label rules,
see [Preference Schema](preference-schema.md). For agent operating boundaries,
see [Agent Instructions](../AGENTS.md).

## Boundaries

- Read from `/path/to/stringartio/experiments`.
- Read StringArtio's `docs/string-art/generation-quality-contract.json` for
  suggestion constraints and metadata that StringArtio later cross-checks in
  handoff runs.
- Write only inside this repository's `data/` folder by default.
- Do not edit StringArtio JS, Rust, native module, docs, generated output, or
  experiment results.
- Do not execute `scripts/stringArtExperimentRunner.mjs` from optimization.

## Candidate Manifest

The manifest is source-level, not only config-level. A single experiment config
rendered for four source images becomes four candidate rows so blind review can
compare candidates for the same source.

Each row contains:

- `run_id`
- `candidate_id`
- `source_id`
- `source_hash`
- `config`
- `metrics`
- `artifact_paths`
- `runtime_ms` (source-level artifact runtime; batch `totalMs` is normalized by
  artifact count when an experiment episode rendered multiple sources or
  repeats)
- `line_count`
- `preset`
- `lane`
- `app_ready`
- `metadata.rendered_svg` when an output SVG artifact exists or was expected

`metadata.rendered_svg` is extracted from existing `artifact_paths.output` SVG
files with standard-library XML parsing. It records rendered line/stroke count,
stroke opacity min/mean/max, stroke width min/mean/max, missing default counts,
validity, and warning counts. Missing JSON or image/SVG files become warnings
in the manifest; malformed SVG files also appear in rendered SVG diagnostics.

## Feature Table

`features.csv` contains stable identifiers plus numeric columns from:

- existing metrics,
- candidate config,
- artwork quality sidecars,
- geometry summaries,
- dimension scores,
- rendered SVG diagnostics,
- future residual/calibration/local-search trace metrics when existing
  artifacts emit them.

Non-numeric values are left out of model features.

Residual metrics such as `residualLumaScore`, `residualRgbScore`,
`renderedResidualLumaScore`, and `renderedResidualRgbScore` are exported for
inspection but are diagnostic-only by default. The baseline model excludes
feature columns whose metric name contains `residual` until an ablation shows
that those fields improve agreement with human labels.

## Robustness Source Suite

`source-suite` creates an optional local photo suite under
`data/source_suite/robustness/` for manual generalization checks. The suite
covers faces, pets, objects, low-contrast/fog, backlight, complex backgrounds,
dark backgrounds, bright backgrounds, and small off-center subjects. Its
`manifest.json` records source URLs, licenses, attribution, local image paths,
dimensions, and file hashes.

The generated `dataset.json` is a StringArtio-compatible template, but
Preference Lab does not run the generator. A human or StringArtio-owned harness
step must explicitly consume that dataset.

StringArtio may also host a runner-ready robustness dataset at
`experiments/rl-training/robustness/dataset.json`. Preference Lab validates that
copy with `validate-robustness-dataset`, checking the `pair-1` through `pair-9`
ids, the proxy pairs `pair-2` and `pair-4`, and the 1000x1000 source/target
images. The local workspace may expose the same folder through the ignored alias
`data/source_suite/robustness/stringartio-runner/`. This dataset is
robustness/generalization input, not a promotion conclusion; promising runs
still need blind review and comparison artifacts.

## Reward Model

The baseline model uses pairwise logistic ranking in the Bradley-Terry family.
It trains on feature differences:

```text
features(candidate A) - features(candidate B) -> human winner
```

`tie` labels do not say either candidate is good; they say the candidates are
similar enough that the score difference should be small. The baseline model
therefore trains on `tie` as a weak equality loss with lower weight than an
explicit A/B winner.

`both_bad` labels do not express a relative winner, so the model treats each
candidate in that pair as a failure example against a neutral feature baseline
and applies an explicit failure penalty to that candidate's score.

`reason_flags` are not cosmetic metadata. When present, the model adds
lower-weight auxiliary examples that mask the feature difference down to numeric
columns related to the selected flags. For example, `less_clumping` emphasizes
`metric_line_clump_penalty` and `metric_overdraw_rate`, while `better_contrast`
emphasizes contrast-related metric/config columns. This lets the reviewer say
which visible quality dimension drove the label without changing the required
A/B/tie/both_bad winner.

`better_visibility` is the visibility-specific reason flag. It maps to rendered
SVG stroke opacity/width, derived visible-ink score, config-level visibility
settings, and contrast fields when those columns are present. It can explain an
A/B winner with better app/export visibility or a `both_bad` pair where both
candidates are too faint.

When there are too few labels, it emits a fallback model rather than failing.

## Review Queue

The review queue remains same-source and blind, but after a model exists it is
failure-aware. It tries to pair uncertain or risky candidates with app-ready,
low-failure anchors instead of repeatedly pairing two candidates that both look
likely to produce `both_bad` labels. The default selection target reserves at
least 40% of a batch for anchor-mixed pairs when enough such pairs are
available. Selected rows are interleaved by `source_id` so review batches keep
multiple source images represented before reusing one source heavily. Visual
risk includes rendered SVG opacity/width diagnostics when present, so a
config-safe candidate can still be reviewed sooner if its actual SVG artifact
looks faint or malformed.

## Optimization

The suggestion engine is a constrained preference-guided search, not Bayesian
Optimization. It uses observed app-ready candidates as anchors, perturbs config
values inside observed ranges, estimates preference from the sidecar model,
and writes suggestion JSON. The acquisition value is a transparent heuristic;
there is no Gaussian-process posterior.

StringArtio owns the generation-quality contract. The optimizer consumes that
contract for runtime, line-count, visibility, preferred line range, and
forbidden target-aware fields, then records the contract version/hash/source in
`suggested-configs.json`. If the contract is unavailable, the optimizer falls
back to bundled defaults and emits a warning.

StringArtio validates the suggestion file metadata on regeneration. Matching
hashes are quiet; missing, fallback, or mismatched contract references are
carried forward as warnings in the StringArtio manifest source metadata.

Suggestion anchors must also satisfy runtime, line-count, target-awareness, and
visible-rendering floors so score-attractive but nearly invisible thread output
does not seed the next pass.

Visibility uses two thresholds. The minimum floor rejects faint anchors
(`visualOpacityScale >= 0.60`, `visualWidthScale >= 0.80`,
`lineInk >= 0.0085`, and visible-ink product `>= 0.0040`). Emitted
suggestions are then raised to a separate app-upload target
(`visualOpacityScale >= 0.70`, `visualWidthScale >= 0.90`,
`lineInk >= 0.0090`, and visible-ink product `>= 0.0055`) so candidates do
not sit directly on the rejection floor.

The line-count limit remains a hard constraint, but default suggestions are
steered toward a 5200 to 5800 moderate-density band. This keeps the optimizer
from treating 6000-line high-density configs as the default fix for faintness.

When `both_bad` failure signals exist, the optimizer prefers stable base
candidates with no observed `both_bad` count before falling back to
failure-observed bases. Stable bases are interleaved by `source_id` before the
optimizer reuses another anchor from the same source image, reducing the chance
that one high-scoring source dominates the next suggestion packet.

Suggestion base scoring also includes rendered SVG visibility risk. This is not
a hard promotion constraint and it is not a human preference label; it is extra
diagnostic evidence used to avoid seeding future suggestions from candidates
whose exported SVG strokes are faint or malformed.

Suggestion provenance includes the base candidate's config visible-ink score
and rendered SVG statistics when available. Each suggestion keeps
`experiment_intent: "preference_tuning_suggestion"` and lists supported
handoff intents for future StringArtio-owned experiments:

- `render_model_calibration`
- `bounded_add_remove_local_search`
- `conservative_auto_color`

These handoff intents are metadata only. This repository still does not execute
generator runs, calibration runs, local-search passes, or color-analysis
experiments.

It does not execute JS experiments.

Generator re-runs, closed-loop automation, and Reinforcement Learning are
outside this repository's default scope. Those boundaries are repeated in
[Agent Instructions](../AGENTS.md), [Claude guide](../CLAUDE.md),
[Codex guide](../CODEX.md), and [Gemini guide](../GEMINI.md) so coding agents
do not accidentally expand the lab beyond steps 1 through 7.
