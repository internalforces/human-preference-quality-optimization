# Preference Schema

This file defines the append-only human label format used by the HPL pipeline.
For the full pipeline, see [Data Flow](data-flow.md). For model and optimizer
boundaries, see [Architecture](architecture.md) and
[Agent Instructions](../AGENTS.md).

`preferences.jsonl` is append-only. Each line is one JSON object.

Required fields:

- `preference_id`
- `source_id`
- `candidate_a`
- `candidate_b`
- `winner`

Allowed winners:

- `A`
- `B`
- `tie`
- `both_bad`

Reviewer decision guidelines:

- Choose `A` when candidate A is clearly preferred over candidate B for the
  same source image. Typical reasons include a sharper face, more readable
  hair, a better outline, stronger contrast, cleaner line placement, less blur,
  or less line clumping.
- Choose `B` under the same standard when candidate B is clearly preferred over
  candidate A.
- Choose `tie` when the two candidates are close enough that a forced winner
  would be noise. A tie can mean both are similarly good, both are merely
  acceptable, or their tradeoffs cancel out. It does not mean either candidate
  is globally good.
- Choose `both_bad` when neither candidate should be promoted as a useful
  result. Examples include unreadable facial structure, severe clumping,
  excessive blur, broken outlines, unusable contrast, or generally failed line
  distribution.

Review process:

- Review `blind_artifacts` first and make the A/B/tie/both_bad decision before
  looking at diagnostics.
- Use `diagnostic_artifacts` only after the blind decision to fill in
  `reason_flags` and `notes`.
- Prefer `tie` over a forced A/B winner when the visible difference is too
  small to defend.
- Prefer `both_bad` over `tie` when both candidates are unusable, even if one is
  slightly less bad.

Reviewer agreement:

- `reviewer` must be a stable person-level alias, not a UI name or collection
  channel.
- At least two independent reviewers must rate some identical unordered
  candidate pairs. A/B orientation may be swapped; the evaluator canonicalizes
  the winning candidate before computing agreement.
- The evaluator reports exact agreement and chance-corrected kappa. With no
  shared pairs, both are reported as unavailable rather than estimated from
  unrelated reviews.

Static review browser export:

- A reusable review browser may export one JSONL record per selected card, but
  the exported records must still follow this append-only schema.
- Reviewer-facing HTML may use Korean labels and descriptions. Keep exported
  field names and schema values unchanged, especially `A`, `B`, `tie`,
  `both_bad`, and schema-defined `reason_flags` values.
- Exported records should include `preference_id`, `source_id`, `candidate_a`,
  `candidate_b`, `winner`, `reviewer`, `timestamp`, `reason_flags`, and
  `notes`.
- The browser may persist in-progress selections in `localStorage`, but that
  state is temporary and is not a preference dataset.
- The browser should capture reason checkboxes and free-text notes after the
  blind choice. These fields explain the selected winner, `tie`, or `both_bad`
  decision; they do not replace the required `winner`.
- Do not append exported records until a human reviewer has made the choices.
  Model scores, ranking metrics, or queue priority values are not labels.
- After appending exported records to `data/preferences/preferences.jsonl`, run
  `validate-preferences`.

Optional fields:

- `reviewer`
- `timestamp`
- `reason_flags`
- `notes`
- `review_context` (tracked review UI provenance; older records may omit it)

The current `review_context` object contains `interface`,
`interface_schema_version`, `queue_id`, and `blind_first`. These fields make
the review surface and source queue traceable without changing winner semantics.

Reason flags:

- `sharper_face`
- `better_hair`
- `better_outline`
- `better_contrast`
- `cleaner`
- `less_blurry`
- `less_clumping`
- `better_visibility`

Reason flag meanings:

- `sharper_face`: the face or primary subject structure is more legible.
- `better_hair`: hair detail or hair silhouette is more readable.
- `better_outline`: the major silhouette and object boundaries hold together
  better.
- `better_contrast`: light and dark regions separate more clearly.
- `cleaner`: line placement has less visual noise or fewer distracting marks.
- `less_blurry`: the overall image impression is less smeared or soft.
- `less_clumping`: lines are less over-concentrated in one area.
- `better_visibility`: the thread output is easier to see in the app/exported
  artifact, including stronger rendered stroke opacity, wider visible strokes,
  stronger visible-ink settings, or better contrast.

For `A` and `B` labels, reason flags describe why the winner was preferred. For
`tie`, they describe dimensions where the candidates were effectively equal or
where neither side had a defensible advantage. For `both_bad`, they describe
quality dimensions that failed badly enough to reject both candidates.

Rules:

- Candidate A and B must be different.
- Candidate A and B must share the same `source_id`.
- `tie` records are retained and used as weak equality signals, meaning the two
  candidates should receive similar preference scores.
- `both_bad` records are retained and used as candidate-level failure signals,
  not as A-vs-B winner labels.
- `reason_flags` are optional, but when present they are used by
  `train-model` as lower-weight auxiliary feature losses on related numeric
  metrics. They are not a substitute for the required `winner` label.
- `better_visibility` maps to rendered SVG stroke opacity/width diagnostics,
  derived visible-ink score, config-level visibility settings, and contrast
  metrics when those feature columns are available. For `both_bad`, it means
  visibility was one of the failed dimensions for both candidates.
