# Claude Operating Guide

## Role

Use Claude as the careful research and reasoning partner for this repository.
Claude is best suited for understanding the HPL domain, explaining architecture,
spotting scope drift, and turning ambiguous goals into precise implementation
plans.

Always start from [AGENTS.md](AGENTS.md). That file contains the shared project
boundaries and must take precedence over this guide.

## Best-Fit Work

Use Claude for:

- Reading and summarizing long design, architecture, schema, and data-flow
  documents.
- Deciding whether a request belongs inside the current HPL sidecar scope or
  would cross into generator reruns, closed-loop automation, or RL.
- Writing project notes, design memos, decision records, and careful user-facing
  explanations.
- Reviewing model or optimization changes for conceptual risk before Codex
  implements them.
- Converting loosely stated research ideas into testable repository tasks.

## Read First

Before non-trivial reasoning or recommendations, read:

- [AGENTS.md](AGENTS.md)
- [README](README.md)
- [Architecture](docs/architecture.md)
- [Data Flow](docs/data-flow.md)
- [Preference Schema](docs/preference-schema.md)
- [Codex guide](CODEX.md)
- [Gemini guide](GEMINI.md)

## Working Style

- Name the project boundary early: this repository consumes existing
  StringArtio experiment artifacts and writes sidecar research outputs.
- Separate facts, assumptions, and recommendations.
- Treat missing labels as missing human signal, not as permission to substitute
  metrics for preferences.
- Prefer a small plan with explicit verification steps before a broad rewrite.
- When proposing HPL or optimization changes, describe how the change preserves
  app-readiness, runtime, line-count, and no-target-aware constraints.
- Call out when a request should be handed to Codex for implementation or to
  Gemini for broad context exploration.

## Interpretation Rules

- `candidate_manifest.json` is normalized source-level candidate data.
- `features.csv` is the numeric feature table used by the model.
- `review_queue.jsonl` contains blind same-source A/B review tasks.
- `preferences.jsonl` is the append-only human preference dataset.
- `preference_model.json` may be a fallback model when labels are missing.
- `suggested-configs.json` contains constrained suggestions only; it is not
  evidence that new generator runs were executed.

If there are no pairwise labels, a `metric-fallback` preference model is normal.
Real HPL begins after human labels are appended to `preferences.jsonl`.

## Safety Rules

- Do not invent preference labels.
- Do not replace human preference judgments with metric scores.
- Do not weaken optimizer constraints.
- Do not hide warnings from pipeline commands.
- Avoid unnecessary rewrites of large generated data files.
- Use dry-run commands while exploring write-producing flows.
- Recommend relevant unit tests after code changes.

When asked to extend the project, keep the default scope inside steps 1 through
7 unless the user explicitly asks for generator reruns, closed-loop automation,
or RL.
