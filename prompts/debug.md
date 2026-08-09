# Debug Prompt Template

**Role:** Implementer
**Note:** A Researcher may assist with broad scanning, but the Implementer owns the fix.
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
