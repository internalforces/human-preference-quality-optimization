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
