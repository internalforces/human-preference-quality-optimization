# Generate Candidate 09B On Robustness Suite

You are working in the StringArtio app repository:

```text
/path/to/stringartio
```

Goal: regenerate the human-preferred Preference Lab review candidate "09B" on the 9-image robustness source suite, then report the generated artifacts so Preference Lab can ingest them for HPL review.

## Context

Preference Lab review 09B was selected by the human reviewer as app-sale-ready quality.

Observed candidate:

```text
candidate_id: 20260624080512:20260623230513:1::pair-1::85daa07640
run_id: 20260624080512
phase/group: 20260623230513:1
preset: clean-gamma-bg-direct-validation
lane: app-ready-clean
profile: clean
app_ready: true
line_count: 6000
runtime_ms_per_source: 16308.125
```

Known source artifact:

```text
/path/to/stringartio/experiments/local-runs/20260624080512/outputs/20260623230513/clean/001-r1-pair-1-score-0-535672.svg
```

Use this exact candidate configuration:

```json
{
  "backgroundSuppressionStrength": 0.12,
  "detailDarkenStrength": 0,
  "detailSharpenStrength": 0,
  "finalLineCap": 6000,
  "foregroundFocusStrength": 0.24,
  "pinCount": 600,
  "qualityModeKey": "clean",
  "targetAwareLineReweighting": false,
  "targetGuidanceStrength": 0,
  "threadCount": 6000,
  "threadThickness": 7,
  "visualOpacityScale": 1,
  "visualTaperStartRatio": 1,
  "visualTaperStrength": 0,
  "visualWidthScale": 1
}
```

Robustness dataset to run:

```text
/path/to/stringartio-preference-lab/data/source_suite/robustness/dataset.json
```

It contains these 9 source IDs:

```text
robust-face-portrait
robust-pet-cat
robust-object-camera
robust-low-contrast-fog
robust-backlit-silhouette
robust-complex-background
robust-dark-background
robust-bright-background
robust-small-offcenter-subject
```

## Hard Boundaries

- Do not edit Preference Lab source code.
- Do not claim these outputs are promoted or sale-ready until the generated artifacts pass StringArtio app-ready checks and human review.
- Do not add target-aware logic.
- Keep `targetAwareLineReweighting=false` and `targetGuidanceStrength=0`.
- Preserve app-ready/runtime/line-count evidence in the run summary.
- If another StringArtio experiment is active, inspect status first and ask before stopping it.

## Suggested Procedure

1. Create a temporary Preference Lab suggestions file inside StringArtio, for example:

```text
experiments/rl-training/preference-lab-09b-robustness-suggestion.json
```

Use this content:

```json
{
  "schema_version": 1,
  "created_at": "2026-07-03T09:15:00Z",
  "constraints": {
    "app_ready": true,
    "auto_execute_js_experiments": false,
    "line_count_limit": 6000,
    "no_target_aware_logic": true,
    "runtime_limit_ms": 30000
  },
  "input": {
    "source": "Preference Lab review 09B human-selected candidate",
    "observed_candidate_id": "20260624080512:20260623230513:1::pair-1::85daa07640",
    "observed_run_id": "20260624080512"
  },
  "suggestions": [
    {
      "suggestion_id": "hpl-review09-b-app-ready-clean-6000",
      "expected_preference_score": null,
      "nearest_observed_candidate": "20260624080512:20260623230513:1::pair-1::85daa07640",
      "source_run_id": "20260624080512",
      "config": {
        "backgroundSuppressionStrength": 0.12,
        "detailDarkenStrength": 0,
        "detailSharpenStrength": 0,
        "finalLineCap": 6000,
        "foregroundFocusStrength": 0.24,
        "pinCount": 600,
        "qualityModeKey": "clean",
        "targetAwareLineReweighting": false,
        "targetGuidanceStrength": 0,
        "threadCount": 6000,
        "threadThickness": 7,
        "visualOpacityScale": 1,
        "visualTaperStartRatio": 1,
        "visualTaperStrength": 0,
        "visualWidthScale": 1
      }
    }
  ],
  "warnings": [
    "Manual replay packet for robustness generation; not an optimizer-generated suggestion batch."
  ]
}
```

2. Run the StringArtio experiment runner against the 9-image robustness dataset:

```bash
cd /path/to/stringartio

npm run experiment:string-art -- start \
  --preset=preference-lab-suggestions \
  --dataset=/path/to/stringartio-preference-lab/data/source_suite/robustness/dataset.json \
  --suggestions-path=experiments/rl-training/preference-lab-09b-robustness-suggestion.json \
  --suggestion-ids=hpl-review09-b-app-ready-clean-6000 \
  --suggestion-repeats=1 \
  --suggestion-sample-size=192 \
  --suggestion-comparison-size=192 \
  --suggestion-runtime-target-ms=30000 \
  --max-minutes=120
```

3. When the run finishes, summarize it:

```bash
npm run experiment:string-art -- summarize --run-id=<runId>
```

4. Report back:

- `runId`
- path to `manifest.json`
- path to `results.json`
- path to `artwork-quality-summary.json`
- path to `preference-lab-handoff.json`
- output SVG and comparison PNG paths for all 9 robustness source IDs
- app-ready/runtime/line-count warnings, if any
- whether every source produced exactly one repeat

5. After this, Preference Lab should run:

```bash
cd /path/to/stringartio-preference-lab
PYTHONPATH=src python3 -m stringartio_preference_lab ingest
PYTHONPATH=src python3 -m stringartio_preference_lab features
PYTHONPATH=src python3 -m stringartio_preference_lab queue --limit=50
```

Then generate a new HPL HTML review page from the refreshed queue.
