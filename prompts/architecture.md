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
