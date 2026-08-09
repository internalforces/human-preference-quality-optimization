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
