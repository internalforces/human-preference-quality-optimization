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
