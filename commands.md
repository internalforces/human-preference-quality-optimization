# Commands

Single source of truth for all execution commands. Run all commands from the repository root.

---

## Setup

Install in an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[dev]'
```

Validate configuration and create required directories:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab validate-config --create-dirs
```

---

## Test

Run the full test suite:

```bash
python3 -m unittest discover -s tests
```

Run tests with branch coverage (CI requires at least 75%):

```bash
python3 -m coverage run -m unittest discover -s tests
python3 -m coverage report
```

Reproduce the tracked anonymized public fixture without installation:

```bash
./scripts/reproduce_public_evaluation.sh
```

The demo intentionally warns that the fixture has three labeled sources and no
repeated candidate pair across reviewer identifiers. It writes only under
`examples/demo-output/`; generated suggestions remain marked `not_executed`.

---

## Pipeline

Build or refresh the diverse robustness source image suite. This writes a
StringArtio-compatible dataset template under `data/source_suite/robustness/`
without running any generator:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab source-suite
```

Validate the runner-ready robustness dataset prepared in the StringArtio app
repository. This only reads JSON/images and does not run the generator:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab validate-robustness-dataset
```

The same folder is available in this workspace through the ignored alias
`data/source_suite/robustness/stringartio-runner/`.

Manual StringArtio runner command for that dataset, run from the app repository
only when explicitly starting an experiment:

```bash
cd /path/to/stringartio
npm run experiment:string-art -- start \
  --dataset=experiments/rl-training/robustness/dataset.json \
  --preset=clean-app-ready \
  --max-minutes=75
```

Treat this 9-image set as robustness/generalization input. Do not change app
defaults from metrics alone; if results look promising, create blind review and
comparison artifacts before promotion decisions.

Run pipeline steps individually in order:

```bash
# 1. Ingest StringArtio experiment artifacts into the candidate manifest
PYTHONPATH=src python3 -m stringartio_preference_lab ingest

# Ingest exactly one local run by run id, useful before adding robustness runs
PYTHONPATH=src python3 -m stringartio_preference_lab ingest --run-id=20260703195834 --dry-run

# 2. Extract numeric features from the candidate manifest
PYTHONPATH=src python3 -m stringartio_preference_lab features

# 3. Generate the blind pairwise review queue (adjust --limit as needed)
PYTHONPATH=src python3 -m stringartio_preference_lab queue --limit=50

# 4. Validate human preference labels before model training
PYTHONPATH=src python3 -m stringartio_preference_lab validate-preferences

# 5. Train the preference/reward model from validated labels
PYTHONPATH=src python3 -m stringartio_preference_lab train-model

# 6. Generate constrained preference-guided search suggestions (not GP-based BO)
PYTHONPATH=src python3 -m stringartio_preference_lab suggest --limit=10
```

Evaluate the metric baseline and preference-model ablations with source and run
holdouts, source-level bootstrap confidence intervals, and reviewer agreement:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab evaluate \
  --output=portfolio/evaluation-report.json
```

The generator remains manual. After a suggestion is run by a human in the
StringArtio repository, follow `docs/manual-suggestion-evaluation.md` for the
untouched-source blind comparison.

Start the tracked, append-only blind review UI:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab review --port=8765
```

---

## Dry Run

Run the full pipeline without writing any output files:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

Use this before any write-producing pipeline run when exploring or verifying behavior.

---

## Lint and Format

No formatter is enforced yet. CI compiles every Python source file and runs the
test/coverage gate.

---

## Benchmark and Export

No dedicated benchmark or export commands yet. Add entries here when introduced.

---

## Release

No automated release process yet. Add entries here when introduced.
