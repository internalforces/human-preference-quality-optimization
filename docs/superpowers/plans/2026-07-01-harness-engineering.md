# Harness Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the AI Development Harness structure — new directories, files with starter content, and a migration of commands out of AGENTS.md — without changing any pipeline behavior or data formats.

**Architecture:** Flat augmentation at the repository root. Seven new directories/files groups are created. AGENTS.md is modified once to replace its commands section with a pointer to `commands.md`. All other existing files are untouched.

**Tech Stack:** Markdown only. No code changes. No dependency changes.

---

## File Map

### Files to create

| File | Responsibility |
|------|---------------|
| `commands.md` | Single source of truth for all execution commands |
| `ORCHESTRATOR.md` | Multi-agent workflow definitions and approval gates |
| `memory/project.md` | Static project identity and scope |
| `memory/architecture.md` | Concise agent-oriented architectural briefing |
| `memory/decisions.md` | Append-preferred log of architectural decisions |
| `memory/known-issues.md` | Unscheduled problems and known limitations |
| `memory/glossary.md` | Stable project terminology definitions |
| `memory/session.md` | Rolling current-state file for active sessions |
| `memory/sessions/.gitkeep` | Preserves the sessions archive directory in git |
| `tasks/active.md` | Current work in progress, organized by owner |
| `tasks/backlog.md` | Ordered list of tasks not yet started |
| `tasks/completed.md` | Append-only log of finished tasks |
| `reports/.gitkeep` | Preserves the milestone reports directory in git |
| `prompts/implementation.md` | Template for handing implementation tasks to an agent |
| `prompts/review.md` | Template for requesting code or architecture review |
| `prompts/debug.md` | Template for investigating failures |
| `prompts/research.md` | Template for broad exploration and synthesis |
| `prompts/architecture.md` | Template for design and framing work |

### Files to modify

| File | Change |
|------|--------|
| `AGENTS.md` | Replace `## Development Commands` section with a two-line pointer to `commands.md` |

---

## Task 1: Migrate commands to `commands.md` and update `AGENTS.md`

**Files:**
- Create: `commands.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Create `commands.md`**

Create the file at the repository root with this exact content:

```markdown
# Commands

Single source of truth for all execution commands. Run all commands from the repository root.

---

## Setup

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

---

## Pipeline

Run pipeline steps individually in order:

```bash
# 1. Ingest StringArtio experiment artifacts into the candidate manifest
PYTHONPATH=src python3 -m stringartio_preference_lab ingest

# 2. Extract numeric features from the candidate manifest
PYTHONPATH=src python3 -m stringartio_preference_lab features

# 3. Generate the blind pairwise review queue (adjust --limit as needed)
PYTHONPATH=src python3 -m stringartio_preference_lab queue --limit=50

# 4. Validate human preference labels before model training
PYTHONPATH=src python3 -m stringartio_preference_lab validate-preferences

# 5. Train the preference/reward model from validated labels
PYTHONPATH=src python3 -m stringartio_preference_lab train-model

# 6. Generate constrained Bayesian Optimization suggestions
PYTHONPATH=src python3 -m stringartio_preference_lab suggest --limit=10
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

No linter is currently configured. Add entries here when one is introduced.

---

## Benchmark and Export

No dedicated benchmark or export commands yet. Add entries here when introduced.

---

## Release

No automated release process yet. Add entries here when introduced.
```

- [ ] **Step 2: Verify `commands.md` contains all migrated commands**

```bash
grep -c "python3 -m stringartio_preference_lab" commands.md
```

Expected: `8` (validate-config, ingest, features, queue, validate-preferences, train-model, suggest, pipeline)

- [ ] **Step 3: Remove the `## Development Commands` section from `AGENTS.md` and replace with a pointer**

Find this block in `AGENTS.md` (lines ~136–160):

```
## Development Commands

Run commands from the repository root:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab validate-config --create-dirs
...
```

Dry-run pipeline:
...

Tests:
...
```

Replace it with:

```markdown
## Commands

See [`commands.md`](commands.md) for the complete command reference, including setup, testing, pipeline steps, dry-run, and future lint, benchmark, and release commands.
```

- [ ] **Step 4: Verify `AGENTS.md` no longer contains the raw command block**

```bash
grep -c "PYTHONPATH=src" AGENTS.md
```

Expected: `0`

- [ ] **Step 5: Verify `commands.md` is referenced from `AGENTS.md`**

```bash
grep "commands.md" AGENTS.md
```

Expected: one line containing `commands.md`

- [ ] **Step 6: Commit**

```bash
git add commands.md AGENTS.md
git commit -m "feat: migrate commands to commands.md, update AGENTS.md with pointer"
```

---

## Task 2: Create `ORCHESTRATOR.md`

**Files:**
- Create: `ORCHESTRATOR.md`

- [ ] **Step 1: Create `ORCHESTRATOR.md`**

```markdown
# Orchestrator

Defines standard multi-agent workflows for this repository.

**Current mode:** Human-guided. A human reads this document and delegates steps to agents manually.  
**Future mode:** Compatible with automated orchestration without restructuring. See the design spec for details (`docs/superpowers/specs/2026-07-01-harness-engineering-design.md`, Section 9).

Agent names below are role labels, not model names. They remain valid if the underlying models change.

---

## Roles

| Role | Current agent | Responsibility |
|------|--------------|---------------|
| Planner | Claude | Requirement analysis, scope check, architecture, risk |
| Implementer | Codex | Implementation, tests, debugging, refactoring |
| Reviewer | Claude or Codex | Code review, correctness, missing coverage |
| Researcher | Gemini | Broad scan, synthesis, alternative approaches |

---

## Human Approval Gates

Stop and get explicit human approval before:

- Modifying the sibling StringArtio app or its generated artifacts
- Deleting or overwriting data files in `data/`
- Schema changes to `preferences.jsonl` or `candidate_manifest.json`
- Changes to model training strategy or optimizer constraints
- Release preparation

Record the approval decision in `memory/session.md` before continuing.

---

## Workflow: Feature

Use when adding a new capability to the pipeline.

```
Human request
  ↓
Planner — requirement analysis, scope check against AGENTS.md boundaries
  ↓
Human approval gate — confirm scope before implementation begins
  ↓
Implementer — implementation, unit tests, dry-run verification
  ↓
Reviewer — code review, correctness, missing test coverage
  ↓
Researcher — alternatives considered, known prior art (if needed)
  ↓
Human final approval
  ↓
Implementer — commit and update tasks/completed.md
  ↓
Assigned agent — create milestone report in reports/ and archive session
```

**Handoff note:** When passing work between agents, include: files changed, commands run, warnings observed, unresolved assumptions.

---

## Workflow: BugFix

Use when diagnosing and fixing an unexpected behavior.

```
Human report or known-issue promotion
  ↓
Planner — framing, risk assessment, scope check
  ↓
Implementer — root cause diagnosis, fix, focused test
  ↓
Reviewer — review fix and test for correctness
  ↓
Human approval (if fix touches an approval-gated area)
  ↓
Implementer — commit and update tasks/completed.md
  ↓
Assigned agent — update memory/known-issues.md if the issue is now closed
```

---

## Workflow: Research

Use when exploring a question before making a design decision.

```
Human question
  ↓
Researcher — broad scan, synthesis, evidence from repository files and artifacts
  ↓
Planner — judgment, recommendation, risk
  ↓
Human decision
  ↓
Planner — record decision in memory/decisions.md
```

---

## Adding New Workflows

Add a new `## Workflow: <Name>` section following the same structure:
1. When to use it
2. Step sequence with role labels
3. Approval gates (if any)
4. Handoff notes

Do not remove existing workflows when adding new ones.
```

- [ ] **Step 2: Verify `ORCHESTRATOR.md` exists and contains the three workflows**

```bash
grep "^## Workflow:" ORCHESTRATOR.md
```

Expected:
```
## Workflow: Feature
## Workflow: BugFix
## Workflow: Research
```

- [ ] **Step 3: Commit**

```bash
git add ORCHESTRATOR.md
git commit -m "feat: add ORCHESTRATOR.md with feature, bugfix, and research workflows"
```

---

## Task 3: Create `memory/` files

**Files:**
- Create: `memory/project.md`
- Create: `memory/architecture.md`
- Create: `memory/decisions.md`
- Create: `memory/known-issues.md`
- Create: `memory/glossary.md`
- Create: `memory/session.md`

- [ ] **Step 1: Create `memory/project.md`**

```markdown
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
```

- [ ] **Step 2: Create `memory/architecture.md`**

```markdown
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
```

- [ ] **Step 3: Create `memory/decisions.md`**

```markdown
# Decisions

> Append-preferred log of significant architectural and design decisions.
> Do not change the meaning of past entries. Minor editorial corrections (typos, formatting, broken links) are acceptable.

---

## 2026-07-01 — Adopt AI Development Harness Engineering structure

**Decision:** Add `memory/`, `tasks/`, `reports/`, `prompts/`, `commands.md`, and `ORCHESTRATOR.md` to the repository root using a flat augmentation approach.

**Rationale:** Multiple AI agents (Claude, Codex, Gemini) work across long-running sessions with significant context loss between sessions. A harness structure provides persistent memory, explicit task state, reusable prompt templates, and a single source of truth for commands — reducing repeated re-explanation and inconsistent agent behavior.

**Alternatives considered:**
- Harness subdirectory (`harness/`): rejected because AI agents that auto-read root-level files would need explicit instruction to look in a subdirectory, adding a navigation layer without benefit.
- Minimal extension (memory + tasks only): rejected because it deferred the prompt library and orchestrator, which are needed to establish consistent workflows now.

**Spec:** `docs/superpowers/specs/2026-07-01-harness-engineering-design.md`
```

- [ ] **Step 4: Create `memory/known-issues.md`**

```markdown
# Known Issues

> Unscheduled problems, known limitations, and deferred work.
> Update when issues are discovered or resolved.
> When an issue is prioritized, move it to `tasks/backlog.md`.

---

<!-- Add entries below. Format:
## [YYYY-MM-DD] Brief title

**Symptom:** What the problem looks like.
**Impact:** Who or what is affected.
**Root cause:** What is known or suspected.
**Status:** Open / Investigating / Deferred / Resolved (YYYY-MM-DD)
-->

_No known issues at this time._
```

- [ ] **Step 5: Create `memory/glossary.md`**

```markdown
# Glossary

> Stable project terminology. Consistent definitions reduce misunderstanding across AI sessions and agents.
> Add new terms when they become stable. Do not rewrite existing definitions without a good reason.

---

**HPL (Human Preference Learning):** The process of collecting pairwise human judgments between candidates and training a preference model from those labels. In this project, HPL covers steps 1–7 of the pipeline.

**Candidate:** A single StringArtio rendering of one source image using one experiment config. Identified by `candidate_id`. Multiple candidates can share the same `run_id` (same config, different source images).

**Source ID (`source_id`):** The identifier for the source image used in a rendering. Pairwise comparisons must share the same `source_id` so the reviewer is comparing the same content rendered differently.

**Preference label:** A human judgment recorded in `preferences.jsonl`. Allowed values: `A` (candidate A is better), `B` (candidate B is better), `tie` (candidates are similar enough that the difference is negligible), `both_bad` (neither candidate is acceptable).

**Reward model / Preference model:** A trained model that predicts which of two candidates a human would prefer. The baseline is a Bradley-Terry-style pairwise logistic ranking model trained on feature differences.

**Blind review:** A review session where the reviewer sees only the rendering artifacts — no config values, metrics, or provenance — before making a preference judgment. Diagnostic artifacts are revealed only after the blind choice is recorded.

**Both-bad:** A preference outcome where neither candidate in a pair meets acceptable quality. Recorded as a failure signal; not treated as an A-vs-B winner by the model.

**Tie:** A preference outcome where two candidates are similar enough that no meaningful preference exists. Treated as a weak equality loss by the model, not as evidence that either candidate is good.

**Reason flag:** An optional annotation on a preference label indicating which visual quality dimension drove the judgment (e.g., `less_clumping`, `better_contrast`, `better_visibility`). Used by the model as lower-weight auxiliary training signal.

**Constraint:** A hard requirement that optimization suggestions must satisfy. Defined by the StringArtio generation-quality contract. Includes `app_ready == true`, runtime limit, line-count limit, visibility floors, and prohibition of target-aware logic.

**Generation-quality contract:** A JSON file owned by StringArtio that defines the constraint set for valid experiment configs. The lab reads this file during `ingest` and `suggest` to apply up-to-date constraints without hardcoding them.

**BO (Bayesian Optimization):** The optimization strategy used by the `suggest` step. Explores the config space by balancing predicted preference score with uncertainty, constrained to the app-ready, visibility-safe region.

**Sidecar:** This repository's role. It reads StringArtio artifacts and writes research outputs alongside them without modifying the app or running generator experiments.

**Pipeline step:** One of the seven owned steps: `ingest`, `features`, `queue`, `validate-preferences`, `train-model`, `suggest`, and the `validate-config` setup command.

**Fallback model:** A preference model emitted when human labels are missing or insufficient. Reports clearly that it is a fallback. Real HPL begins after `preferences.jsonl` contains human pairwise labels.

**Rendered SVG diagnostics:** Stroke opacity, stroke width, and line count extracted from output SVG artifacts by the `ingest` step. Used as visual risk signals in queue generation and optimizer base selection. Not a human preference label.

**Visible-ink score:** A derived metric combining `lineInk`, `visualOpacityScale`, and `visualWidthScale`. Used as a proxy for how visible the thread rendering will appear in the app or export. Not a human preference label.
```

- [ ] **Step 6: Create `memory/session.md`**

```markdown
# Current Session

> This file is continuously updated throughout the active session.
> It reflects present working state only — no history.
> At the end of a significant session, archive this file to `memory/sessions/YYYY-MM-DD-brief-title.md`.
> For history, see `memory/sessions/`.

---

## Status

**Date:** 2026-07-01  
**Active task:** Implement AI Development Harness Engineering structure  
**Owner:** Implementer (Codex)  
**Progress:** Implementation plan written. Ready to execute tasks.  
**Blockers:** None  

## Next Steps

1. Execute the harness implementation plan: `docs/superpowers/plans/2026-07-01-harness-engineering.md`
2. Verify all new files exist with correct content
3. Run `python3 -m unittest discover -s tests` to confirm no regressions
4. Archive this session to `memory/sessions/2026-07-01-harness-setup.md`

## Context for the Next Agent

- Spec approved at v3: `docs/superpowers/specs/2026-07-01-harness-engineering-design.md`
- Implementation plan: `docs/superpowers/plans/2026-07-01-harness-engineering.md`
- No pipeline behavior or data formats are changing in this pass
- AGENTS.md commands section will be replaced with a pointer to `commands.md`
- All new files should have real starter content — no empty placeholders except `.gitkeep` files
```

- [ ] **Step 7: Verify all six `memory/` files exist**

```bash
ls memory/
```

Expected output includes: `project.md  architecture.md  decisions.md  known-issues.md  glossary.md  session.md`

- [ ] **Step 8: Commit**

```bash
git add memory/
git commit -m "feat: add memory/ files with starter content (project, architecture, decisions, known-issues, glossary, session)"
```

---

## Task 4: Create `memory/sessions/` archive directory

**Files:**
- Create: `memory/sessions/.gitkeep`

- [ ] **Step 1: Create the archive directory**

```bash
mkdir -p memory/sessions
touch memory/sessions/.gitkeep
```

- [ ] **Step 2: Verify**

```bash
ls memory/sessions/
```

Expected: `.gitkeep`

- [ ] **Step 3: Commit**

```bash
git add memory/sessions/.gitkeep
git commit -m "feat: add memory/sessions/ archive directory"
```

---

## Task 5: Create `tasks/` files

**Files:**
- Create: `tasks/active.md`
- Create: `tasks/backlog.md`
- Create: `tasks/completed.md`

- [ ] **Step 1: Create `tasks/active.md`**

```markdown
# Active Tasks

> One active task per owner. Update continuously as work progresses.
> When a task completes, move it to `tasks/completed.md` and remove the entry here.

---

## Owner: Implementer (Codex)

**Task:** Implement AI Development Harness Engineering structure  
**Objective:** Create all files defined in the implementation plan without changing pipeline behavior.  
**Priority:** High  
**Progress:** Executing plan tasks sequentially.  
**Blockers:** None  
**Next step:** Continue with remaining plan tasks.  

---

<!-- Add additional owner sections below as needed:

## Owner: [Name]

**Task:** ...
**Objective:** ...
**Priority:** ...
**Progress:** ...
**Blockers:** ...
**Next step:** ...
-->
```

- [ ] **Step 2: Create `tasks/backlog.md`**

```markdown
# Backlog

> Ordered list of tasks not yet started. Pull from the top.
> Human reorders priorities. Agents update status fields.
> When an issue in `memory/known-issues.md` is prioritized, move it here.

| Priority | Title | Objective | Owner | Status | Blocked by |
|----------|-------|-----------|-------|--------|-----------|
| — | — | — | — | — | — |

<!-- Status values: Ready / Blocked / Waiting / Deferred -->

<!-- Add tasks above the placeholder row. Example:
| High | Add linter configuration | Establish consistent code style with ruff or flake8 | Implementer | Ready | — |
-->
```

- [ ] **Step 3: Create `tasks/completed.md`**

```markdown
# Completed Tasks

> Append-only log. Do not edit or remove past entries.
> Link to the session snapshot or milestone report when one exists.

---

<!-- Append entries below. Format:
## YYYY-MM-DD — [Task title]

**Summary:** One or two sentences describing what was done.
**Report / snapshot:** `reports/YYYY-MM-DD-title.md` or `memory/sessions/YYYY-MM-DD-title.md` (if applicable)
-->

_No completed tasks yet._
```

- [ ] **Step 4: Verify all three `tasks/` files exist**

```bash
ls tasks/
```

Expected: `active.md  backlog.md  completed.md`

- [ ] **Step 5: Commit**

```bash
git add tasks/
git commit -m "feat: add tasks/ directory with active, backlog, and completed task files"
```

---

## Task 6: Create `reports/` directory

**Files:**
- Create: `reports/.gitkeep`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p reports
touch reports/.gitkeep
```

- [ ] **Step 2: Verify**

```bash
ls reports/
```

Expected: `.gitkeep`

- [ ] **Step 3: Commit**

```bash
git add reports/.gitkeep
git commit -m "feat: add reports/ directory for milestone reports"
```

---

## Task 7: Create `prompts/` templates

**Files:**
- Create: `prompts/implementation.md`
- Create: `prompts/review.md`
- Create: `prompts/debug.md`
- Create: `prompts/research.md`
- Create: `prompts/architecture.md`

All five templates share a common header structure followed by workflow-specific sections.

- [ ] **Step 1: Create `prompts/implementation.md`**

```markdown
# Implementation Prompt Template

**Role:** Implementer  
**Use when:** Handing a scoped, ready-to-implement task to an agent.  
**Fill in:** All `[BRACKETED]` fields before sending.

---

## Objective

[One sentence: what should be built or changed.]

## Context

[Background the implementer needs. Include: why this task exists, what it connects to, any prior decisions relevant to this work. Reference `memory/decisions.md` if a decision was already made.]

## Relevant Files

- Read before starting: `AGENTS.md`, `memory/project.md`, `memory/session.md`
- Source files to edit: [list exact paths]
- Test files to edit or create: [list exact paths]
- Reference docs: [list any docs/ files relevant to this task]

## Constraints

- Do not weaken any optimizer or preference constraints defined in `AGENTS.md`.
- Do not modify `data/preferences/preferences.jsonl` or fabricate labels.
- Keep data schemas backward-compatible unless the task explicitly requires a schema change.
- Prefer the standard library unless a dependency is clearly justified.
- [Add any task-specific constraints.]

## Files to Edit

[List each file to be created or modified with a one-line description of the change.]

## Test Requirement

[Describe what tests must exist or pass after this task. Be specific: which test file, which behavior. New user-visible pipeline behavior must have a test.]

## Boundary Conditions

[List edge cases, error conditions, or invalid inputs the implementation must handle correctly.]

## Expected Output

[What should exist or be different when the task is complete? Name specific files, commands, or behaviors.]

## Validation

Run these commands to verify the implementation:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

[Add any task-specific validation commands.]

## Success Criteria

- [ ] Tests pass with `python3 -m unittest discover -s tests`
- [ ] Dry-run pipeline completes without errors
- [ ] [Task-specific criterion 1]
- [ ] [Task-specific criterion 2]
- [ ] `tasks/active.md` updated with progress
- [ ] `memory/session.md` updated with outcome
```

- [ ] **Step 2: Create `prompts/review.md`**

```markdown
# Review Prompt Template

**Role:** Reviewer  
**Use when:** Requesting a code or architecture review after implementation.  
**Fill in:** All `[BRACKETED]` fields before sending.

---

## Objective

Review the changes described below for correctness, completeness, risk, and missing test coverage.

## Context

[What was being built and why. Include a link to the task in `tasks/completed.md` or the active entry in `tasks/active.md`.]

## Relevant Files

- Read before starting: `AGENTS.md`, `memory/project.md`, `memory/session.md`
- Files changed: [list exact paths with a one-line description of each change]
- Test files: [list test files added or modified]
- Reference docs: [any docs/ files relevant to the review]

## Constraints

- Hard boundaries in `AGENTS.md` must not be violated.
- Preference data rules (`preferences.jsonl` append-only, no fabricated labels) must be preserved.
- Optimizer constraints must not be weakened.
- [Add any task-specific constraints the reviewer should check against.]

## What Changed

[Describe the change at a behavioral level: what the code does differently now versus before. This is not a diff summary — it is a description of the new behavior.]

## What to Look For

- [ ] Correctness: does the implementation match the stated objective?
- [ ] Edge cases: are boundary conditions handled?
- [ ] Constraint violations: does anything weaken a hard boundary from `AGENTS.md`?
- [ ] Test coverage: is new user-visible behavior tested?
- [ ] Schema compatibility: are data formats backward-compatible?
- [ ] [Task-specific concern 1]
- [ ] [Task-specific concern 2]

## Risk Areas

[List specific areas that feel risky or uncertain. These are the places to review most carefully.]

## Expected Output

A review finding list ordered by severity (High / Medium / Low / Info). For each finding: location, behavioral risk, recommendation.

## Validation

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

## Success Criteria

- [ ] No High-severity findings, or all High findings are acknowledged by the human
- [ ] Tests pass
- [ ] Dry-run pipeline completes without errors
- [ ] Review findings recorded in `memory/session.md`
```

- [ ] **Step 3: Create `prompts/debug.md`**

```markdown
# Debug Prompt Template

**Role:** Implementer or Researcher  
**Use when:** Investigating a failure, unexpected behavior, or warning.  
**Fill in:** All `[BRACKETED]` fields before sending.

---

## Objective

Diagnose the root cause of the symptom described below and recommend or implement a fix.

## Context

[How was this discovered? When did it start? Is it intermittent or consistent?]

## Relevant Files

- Read before starting: `AGENTS.md`, `memory/project.md`, `memory/session.md`, `memory/known-issues.md`
- Suspected files: [list paths most likely involved]
- Test files: [list existing tests for this area]
- Reference docs: [any docs/ files relevant to this behavior]

## Constraints

- Do not fabricate preference labels or weaken optimizer constraints while investigating.
- Use `--dry-run` before any write-producing pipeline command.
- Do not revert user changes unless explicitly asked.
- [Add any task-specific constraints.]

## Symptom

[Describe exactly what goes wrong. Include: command run, error message or unexpected output, expected behavior.]

```
# Example:
# Command run:
PYTHONPATH=src python3 -m stringartio_preference_lab train-model

# Error:
KeyError: 'feature_x' in model.py line 87

# Expected:
Model trains without error and writes preference_model.json
```

## Reproduction Steps

1. [Step 1]
2. [Step 2]
3. [Observed result]

## What Has Already Been Ruled Out

[List what was already investigated so the debugger does not repeat work.]

## Suspected Area

[Name the file, function, or pipeline stage most likely responsible, and why.]

## Expected Output

Root cause identified. Either: (a) a fix implemented and tested, or (b) a findings summary with a recommended fix for human review.

## Validation

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
[Command that reproduces the original symptom — should now pass cleanly]
```

## Success Criteria

- [ ] Root cause identified and documented
- [ ] Fix implemented (or recommendation written for human decision)
- [ ] Tests pass
- [ ] Dry-run pipeline completes without errors
- [ ] `memory/known-issues.md` updated (mark resolved or add new issue if discovered)
- [ ] `memory/session.md` updated with findings
```

- [ ] **Step 4: Create `prompts/research.md`**

```markdown
# Research Prompt Template

**Role:** Researcher  
**Use when:** Exploring a question across many files, artifacts, or alternatives before making a decision.  
**Fill in:** All `[BRACKETED]` fields before sending.

---

## Objective

[One sentence: what question should be answered or what should be compared?]

## Context

[Why is this research needed? What decision will it inform? Link to the relevant entry in `tasks/active.md` or `memory/session.md`.]

## Relevant Files

- Read before starting: `AGENTS.md`, `memory/project.md`, `memory/session.md`
- Primary files to scan: [list exact paths or directories]
- Reference docs: [any docs/ files relevant to the question]
- Artifacts to compare: [list specific data files, JSON outputs, or CSVs if applicable]

## Constraints

- Do not infer human preference labels from metrics or image quality scores.
- Do not treat optimization suggestions as executed experiment results.
- Flag uncertainty instead of filling gaps with invented data.
- Keep source file paths visible in findings so another agent can follow up.
- [Add any task-specific constraints.]

## Question Scope

[Define the boundaries of the research. What is in scope? What is explicitly out of scope?]

## Files to Scan

[List the files or directories to sweep. Be as specific as possible to avoid unnecessary context loading.]

## Output Format Preference

[Describe how findings should be presented. Examples: bullet list of evidence by file, comparison table, narrative summary with citations, grouped as "ready for implementation / needs human decision / needs further research".]

## Expected Output

[What does a complete research output look like? Name the format and the key questions it must answer.]

## Validation

- [ ] All findings cite specific files and line numbers or artifact paths
- [ ] Uncertainty is flagged, not papered over
- [ ] No invented data or inferred labels
- [ ] Output is grouped for easy handoff to Planner or Implementer

## Success Criteria

- [ ] Question is answered with evidence from the repository
- [ ] Findings are formatted as requested
- [ ] Next recommended action is identified (implement / decide / research further)
- [ ] `memory/session.md` updated with research summary
```

- [ ] **Step 5: Create `prompts/architecture.md`**

```markdown
# Architecture Prompt Template

**Role:** Planner  
**Use when:** Designing or evaluating a significant structural or behavioral change before implementation begins.  
**Fill in:** All `[BRACKETED]` fields before sending.

---

## Objective

[One sentence: what architectural question needs to be answered or what design needs to be produced?]

## Context

[Why is this decision being made now? What triggered it? Link to the relevant entry in `memory/decisions.md` if a prior related decision exists.]

## Relevant Files

- Read before starting: `AGENTS.md`, `memory/project.md`, `memory/architecture.md`, `memory/decisions.md`, `memory/session.md`
- Files most relevant to this decision: [list exact paths]
- Reference docs: [any docs/ files relevant to this design area]

## Constraints

- Preserve all hard boundaries in `AGENTS.md` (scope steps 1–7, read-only StringArtio repo, no label fabrication, no constraint weakening).
- Prefer the standard library unless a dependency is clearly justified.
- Keep data schemas backward-compatible where possible.
- [Add any design-specific constraints.]

## Problem Statement

[Describe the problem being solved. What is inadequate about the current design? What capability is needed?]

## Design Options to Explore

[List 2–3 approaches to consider. If you already know you prefer one, say so, but ask the Planner to evaluate all of them.]

1. [Option A]
2. [Option B]
3. [Option C — if applicable]

## What a Good Recommendation Looks Like

[Describe the qualities of an acceptable design output: e.g., "a single preferred approach with explicit trade-offs, a list of files to create or modify, and the criteria for knowing the design is working."]

## Expected Output

A design recommendation including:
- Preferred approach and rationale
- Alternatives considered and why they were not chosen
- Files to create or modify
- Constraints the implementation must satisfy
- Risks and open questions for human decision

## Validation

- [ ] Recommendation stays inside steps 1–7 scope
- [ ] No hard boundaries are weakened
- [ ] Decision recorded in `memory/decisions.md` after human approval
- [ ] Implementation plan created in `docs/superpowers/plans/` before any code is written

## Success Criteria

- [ ] Design is approved by human
- [ ] Decision logged in `memory/decisions.md`
- [ ] Implementation plan exists before Implementer starts work
- [ ] `memory/session.md` updated with design outcome
```

- [ ] **Step 6: Verify all five prompt templates exist**

```bash
ls prompts/
```

Expected: `implementation.md  review.md  debug.md  research.md  architecture.md`

- [ ] **Step 7: Verify all templates contain the common header fields**

```bash
for f in prompts/*.md; do echo "=== $f ==="; grep "^## " "$f"; done
```

Each file should contain at minimum: `## Objective`, `## Context`, `## Relevant Files`, `## Constraints`, `## Expected Output`, `## Validation`, `## Success Criteria`.

- [ ] **Step 8: Commit**

```bash
git add prompts/
git commit -m "feat: add prompts/ directory with five role-oriented, human-first prompt templates"
```

---

## Task 8: Final validation

- [ ] **Step 1: Confirm directory structure matches the spec**

```bash
find . -not -path './.git/*' -not -path './data/*' -not -path './src/*' -not -path './tests/*' -not -path './.idea/*' -not -path './__pycache__/*' | sort
```

Expected to include (among existing files):
```
./commands.md
./ORCHESTRATOR.md
./memory/project.md
./memory/architecture.md
./memory/decisions.md
./memory/known-issues.md
./memory/glossary.md
./memory/session.md
./memory/sessions/.gitkeep
./tasks/active.md
./tasks/backlog.md
./tasks/completed.md
./reports/.gitkeep
./prompts/implementation.md
./prompts/review.md
./prompts/debug.md
./prompts/research.md
./prompts/architecture.md
```

- [ ] **Step 2: Confirm `AGENTS.md` no longer duplicates commands**

```bash
grep -c "PYTHONPATH=src" AGENTS.md
```

Expected: `0`

- [ ] **Step 3: Confirm `commands.md` contains all pipeline commands**

```bash
grep "python3 -m stringartio_preference_lab" commands.md
```

Expected: lines for `validate-config`, `ingest`, `features`, `queue`, `validate-preferences`, `train-model`, `suggest`, `pipeline`

- [ ] **Step 4: Run the test suite to confirm no regressions**

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass

- [ ] **Step 5: Run the dry-run pipeline to confirm no regressions**

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

Expected: completes without errors (warnings about missing labels are normal)

- [ ] **Step 6: Update `tasks/active.md` to reflect completion**

Remove the implementer entry and add a note that the harness setup task is complete.

- [ ] **Step 7: Append to `tasks/completed.md`**

```markdown
## 2026-07-01 — Implement AI Development Harness Engineering structure

**Summary:** Created commands.md, ORCHESTRATOR.md, memory/ files, tasks/ files, reports/ directory, and prompts/ templates. Migrated commands out of AGENTS.md into commands.md. No pipeline behavior or data formats changed.  
**Report / snapshot:** `memory/sessions/2026-07-01-harness-setup.md` (to be written at session end)
```

- [ ] **Step 8: Update `memory/session.md`** to reflect that implementation is complete and the session is ready to archive.

- [ ] **Step 9: Final commit**

```bash
git add tasks/ memory/session.md
git commit -m "chore: mark harness setup complete in tasks and session state"
```

---

## Summary

### Files to create (18)

```
commands.md
ORCHESTRATOR.md
memory/project.md
memory/architecture.md
memory/decisions.md
memory/known-issues.md
memory/glossary.md
memory/session.md
memory/sessions/.gitkeep
tasks/active.md
tasks/backlog.md
tasks/completed.md
reports/.gitkeep
prompts/implementation.md
prompts/review.md
prompts/debug.md
prompts/research.md
prompts/architecture.md
```

### Files to modify (1)

```
AGENTS.md  — replace ## Development Commands section with pointer to commands.md
```

### Migration steps

1. Create `commands.md` with full command content extracted from `AGENTS.md`
2. Replace the commands section in `AGENTS.md` with a two-line pointer
3. Verify no `PYTHONPATH=src` references remain in `AGENTS.md`

### Validation checks

1. `grep -c "PYTHONPATH=src" AGENTS.md` → `0`
2. `grep "python3 -m stringartio_preference_lab" commands.md` → 8 commands present
3. `ls memory/` → 6 files + `sessions/`
4. `ls tasks/` → 3 files
5. `ls prompts/` → 5 files
6. `python3 -m unittest discover -s tests` → all pass
7. `PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3` → no errors

### Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Commands omitted from `commands.md` during migration | Low | Step 1.2 grep check counts all 8 commands |
| `AGENTS.md` edit removes adjacent content | Low | Task 1 verifies the Code Change Guidance section below commands is preserved |
| New markdown files contain broken internal links | Low | All cross-file references use relative paths; verify with final directory listing |
| Tests fail due to import side effects of new directories | Very low | No Python files added; test discovery is unaffected |
