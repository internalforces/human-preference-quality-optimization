# Codex Operating Guide

## Role

Use Codex as the implementation and verification agent for this repository.
Codex is best suited for editing code, running local commands, debugging test
failures, reviewing diffs, and keeping the worktree coherent.

Codex reads [AGENTS.md](AGENTS.md) automatically. Treat that file as the shared
source of truth. This file explains how to apply those rules when Codex is the
agent doing the work.

## Best-Fit Work

Use Codex for:

- Making scoped source, test, and documentation edits.
- Running repository commands and interpreting failures.
- Adding or updating unit tests for user-visible pipeline behavior.
- Reviewing code changes for bugs, regressions, missing tests, and unsafe data
  handling.
- Refactoring only when it reduces real complexity or matches an existing local
  pattern.
- Preparing Git-ready changes after the user asks for commits, branches, or
  pull requests.

Use Claude first when the task is mostly research framing or architecture
judgment. Use Gemini first when the task needs broad context discovery across a
large set of files or artifacts.

## Worktree Discipline

- Inspect the current worktree before editing.
- Do not revert user changes unless explicitly asked.
- Keep changes scoped to the requested behavior.
- Prefer `rg` for file and text search.
- Use existing project patterns before introducing abstractions.
- Do not touch generated artifacts unless the task explicitly requires it.

## Implementation Flow

1. Read [AGENTS.md](AGENTS.md) and the relevant project docs.
2. Inspect nearby code and tests before choosing an implementation.
3. Make the smallest complete change that satisfies the request.
4. Run focused tests first, then broader tests when the change affects shared
   pipeline behavior.
5. Report commands run, warnings observed, and any remaining risk.

Default test command:

```bash
python3 -m unittest discover -s tests
```

Useful dry-run command for write-producing pipeline flows:

```bash
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

## Review Mode

When asked for a review, lead with findings ordered by severity. Reference
specific files and lines, explain the behavioral risk, and mention missing test
coverage when relevant. Keep summaries secondary to actionable findings.

## Boundaries To Enforce

- Never execute the sibling StringArtio generator automatically.
- Never edit the configured StringArtio repository (normally the sibling
  `../stringartio`) by default.
- Never fabricate labels or treat metrics as human preferences.
- Never weaken optimization constraints without explicit user approval.
- Treat `suggested-configs.json` as suggestions only, not executed results.
