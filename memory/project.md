# Project Identity

> Read this file first when starting a new session. It answers: what is this repository and what does it own?

## What This Repository Is

StringArtio Preference Lab is a Python sidecar project for tuning StringArtio with Human Preference Learning (HPL). It reads experiment artifacts produced by the StringArtio app and produces research outputs alongside them.

This repository does **not** run the StringArtio generator, manage the app, or execute automated training loops.

## What This Repository Owns

Steps 1–7 of the HPL loop:

1. Ingest StringArtio experiment artifacts → `candidate_manifest.json`
2. Extract numeric features → `features.csv`
3. Generate active-learning review queue → `review_queue.jsonl`
4. Human preference review → `preferences.jsonl`
5. Validate preference labels
6. Train pairwise preference/reward model → `preference_model.json`
7. Generate constrained Bayesian Optimization suggestions → `suggested-configs.json`

## What Is Out of Scope

- Re-running the StringArtio generator (step 8)
- Closed-loop automated training (step 9)
- Reinforcement Learning (step 10)

Do not add these capabilities unless the user explicitly changes project scope.

## Agent Roster

| Role | Current agent | Best-fit work |
|------|--------------|--------------|
| Planner | Claude | Architecture, design, scope judgment, risk |
| Implementer | Codex | Implementation, tests, debugging, refactoring |
| Researcher | Gemini | Broad scans, synthesis, alternative approaches |

## Key Constraints (never weaken without explicit approval)

- `suggested-configs.json` contains suggestions only — not executed results
- Suggestions must have `app_ready == true`, runtime limit, line-count limit, no target-aware logic
- `preferences.jsonl` is append-only; labels must be human-generated
- `/path/to/stringartio` is read-only by default

## Authoritative References

- Rules and boundaries: `AGENTS.md`
- Architecture detail: `docs/architecture.md`
- Data flow: `docs/data-flow.md`
- Preference schema: `docs/preference-schema.md`
- Commands: `commands.md`
- Workflows: `ORCHESTRATOR.md`
