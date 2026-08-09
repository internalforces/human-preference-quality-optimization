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

Run if research leads to code-level discovery:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m stringartio_preference_lab pipeline --dry-run --limit-runs=3
```

- [ ] All findings cite specific files and line numbers or artifact paths
- [ ] Uncertainty is flagged, not papered over
- [ ] No invented data or inferred labels
- [ ] Output is grouped for easy handoff to Planner or Implementer

## Success Criteria

- [ ] Question is answered with evidence from the repository
- [ ] Findings are formatted as requested
- [ ] Next recommended action is identified (implement / decide / research further)
- [ ] `memory/session.md` updated with research summary
