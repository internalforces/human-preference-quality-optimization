# Manual suggestion-to-baseline blind evaluation

## Status

**Pending manual generator execution and independent human review.** No win rate
is reported until all gates below are complete. Metric improvements and the
existing Track B gallery are not substitutes for this experiment.

Preference Lab intentionally never starts the StringArtio generator. A human
operator runs the approved suggestion in the read-only-by-default StringArtio
repository and returns only completed artifacts for ingestion.

## Primary question

On source images that were not used for reward-model training, suggestion
anchoring, configuration selection, or qualitative debugging, how often is the
suggestion output preferred to the frozen baseline under blind review?

Primary endpoint:

```text
suggestion decisive win rate = suggestion wins / (suggestion wins + baseline wins)
```

Also report tie rate, `both_bad` rate, source-level bootstrap 95% CI, exact
reviewer agreement, and chance-corrected kappa.

## Required design

1. Freeze the model hash, suggestion packet hash, baseline config, runtime and
   line-count limits before looking at holdout results.
2. Reserve at least 10 untouched `source_id` values. Record why every source is
   independent of training, anchor selection, and debugging.
3. Run baseline and suggestion with the same prepared input, seed policy,
   runtime budget, and output resolution. Run StringArtio manually; do not add a
   generator call to Preference Lab.
4. Reject any candidate that violates `app_ready`, runtime, line-count,
   visibility, or no-target-aware constraints before blind review.
5. Randomize A/B orientation per source and hide run/config/metric identity.
6. Use at least two verified independent reviewers. Give every reviewer a
   stable person-level ID and assign at least 20% shared calibration pairs so
   agreement can be estimated.
7. Freeze labels before revealing diagnostics. Preserve `tie` and `both_bad`.
8. Compute the decisive win rate and resample complete sources—not individual
   reviews—for the 95% percentile bootstrap interval.

## Stop and failure rules

- Do not replace a failed suggestion output with a hand-picked alternative.
- Count constraint failures separately and do not silently omit them.
- If fewer than 10 sources complete, label the analysis exploratory.
- If there are no overlapping reviewer pairs, report agreement as unavailable.
- If a reviewer saw candidate identity or metrics before choosing, mark that
  review non-blind and exclude it from the primary analysis.
- Do not change the model or suggestion after inspecting holdout labels.

## Handoff record

Complete `portfolio/suggestion-blind-evaluation.json` with artifact hashes,
source inclusion decisions, counts, CI, reviewer agreement, and failures. Keep
`status` as `pending_manual_run` until the generator artifacts exist, and as
`pending_blind_review` until labels are frozen.

The final report must distinguish:

- automatic metric deltas,
- constraint pass/fail outcomes,
- blind human preference outcomes,
- exploratory observations made after unblinding.
