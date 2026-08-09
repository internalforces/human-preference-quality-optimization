# Agent Instructions

## Purpose

This is the shared operating contract for AI coding agents working in this
repository. Codex reads `AGENTS.md` automatically. Claude and Gemini should
also treat this file as the common source of truth before applying their
agent-specific guidance.

Agent-specific guides:

- [Claude guide](CLAUDE.md): research framing, architecture reasoning, and
  careful scope control.
- [Codex guide](CODEX.md): implementation, test execution, review, and local
  repository operations.
- [Gemini guide](GEMINI.md): broad context scans, cross-document synthesis, and
  exploratory analysis.

If these files disagree, preserve the hard boundaries in this file unless the
user explicitly changes project scope.

## Project Role

This repository is the StringArtio Preference Lab. It is a Python sidecar
project for tuning StringArtio with Human Preference Learning (HPL).

Primary project documentation:

- [README](README.md)
- [Architecture](docs/architecture.md)
- [Data Flow](docs/data-flow.md)
- [Preference Schema](docs/preference-schema.md)
- [Claude guide](CLAUDE.md)
- [Codex guide](CODEX.md)
- [Gemini guide](GEMINI.md)

This repository owns steps 1 through 7 of the preference tuning loop:

1. Read StringArt generator outputs from existing StringArtio experiments.
2. Extract numeric features from candidates.
3. Support Human Preference Learning workflows.
4. Maintain the preference dataset schema and validation.
5. Train reward / preference models from pairwise labels.
6. Generate active-learning review queues.
7. Produce constrained Bayesian Optimization suggestions.

Steps 8 through 10 are outside this repository's default responsibility:

8. Re-running the StringArt generator.
9. Running a fully automated closed training loop.
10. Reinforcement Learning after enough preference data exists.

Do not add automatic generator execution or RL training unless the user
explicitly changes the project scope.

## Hard Boundaries

- Treat the configured StringArtio repository (normally the sibling
  `../stringartio`) as read-only by default.
- Do not edit StringArtio JS, Rust, native, docs, generated outputs, or
  experiment result files from this repository.
- Do not execute `scripts/stringArtExperimentRunner.mjs` or any other
  StringArtio generator runner automatically.
- The optimizer must write suggestion files only.
- Suggestions must keep these constraints:
  - `app_ready == true`
  - runtime limit
  - line-count limit
  - no target-aware logic
  - no automatic JS experiment execution

## Agent Routing

Use each agent where it is strongest:

- Use Claude for problem framing, research notes, architecture explanation,
  project-scope decisions, and long-form documentation.
- Use Codex for concrete edits, tests, debugging, refactors, command execution,
  code review, and Git-oriented repository work.
- Use Gemini for wide context discovery, large document synthesis, alternative
  comparison, and exploratory analysis across many files or artifacts.

No agent should fabricate data, weaken constraints, or treat suggestions as
executed experiment results.

## Pipeline

The normal workflow is:

```text
ingest
  -> features
  -> queue
  -> human preference review
  -> validate-preferences
  -> train-model
  -> suggest
```

The corresponding files are:

- `data/processed/candidate_manifest.json`
- `data/processed/features.csv`
- `data/review_queue/review_queue.jsonl`
- `data/preferences/preferences.jsonl`
- `data/processed/preference_model.json`
- `data/suggestions/suggested-configs.json`

## Preference Data Rules

- `preferences.jsonl` is append-only.
- Each JSONL record is one human review.
- Candidate A and candidate B must be different.
- Candidate A and candidate B must share the same `source_id`.
- Allowed `winner` values are `A`, `B`, `tie`, and `both_bad`.
- Preserve `tie` and `both_bad` records. The baseline model uses `A` / `B`
  winners as strong pairwise labels, uses `tie` as a weak equality loss, and
  uses `both_bad` as a candidate-level failure signal rather than as an A-vs-B
  winner.
- Do not fabricate human labels.
- Do not claim metric scores are human preference labels.
- Reviewers should judge blind artifacts first and use diagnostic artifacts only
  after making the blind choice.

## Modeling And Optimization

- The baseline reward model is a Bradley-Terry-style pairwise logistic model.
- If labels are missing or insufficient, fallback models are acceptable and
  should be reported clearly.
- Active learning is represented by prioritized review queue generation using
  uncertainty, visual risk, and random exploration.
- Constrained BO suggestions should be treated as candidate configs for future
  experiments, not as executed results.
- Never weaken app-readiness, runtime, line-count, or no-target-aware
  constraints without explicit user approval.

## Commands

See [`commands.md`](commands.md) for the complete command reference, including setup, testing, pipeline steps, dry-run, and future lint, benchmark, and release commands.

## Code Change Guidance

- Prefer the standard library unless a dependency is clearly justified.
- Keep generated artifacts stable unless the task explicitly requires
  regenerating them.
- Prefer `--dry-run` before write-producing pipeline commands when exploring.
- Keep data schemas backward-compatible where possible.
- Update docs and tests when changing user-visible pipeline behavior.
- Report warnings from ingestion, preference validation, model training, and
  suggestions instead of hiding them.
- When handing work to another agent, include the files changed, commands run,
  important warnings, and any unresolved assumptions.
