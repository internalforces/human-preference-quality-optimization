# Gemini Operating Guide

@./AGENTS.md

## Role

Use Gemini as the broad-context exploration and synthesis agent for this
repository. Gemini is best suited for sweeping through many files, comparing
alternatives, summarizing large artifacts, and turning scattered evidence into a
clear research brief.

This guide imports [AGENTS.md](AGENTS.md) so Gemini receives the shared project
boundaries before applying these Gemini-specific notes.

## Best-Fit Work

Use Gemini for:

- Wide repository scans before a large documentation or architecture update.
- Comparing multiple pipeline outputs, data artifacts, or experiment summaries.
- Synthesizing long Markdown files, JSON/JSONL records, CSV tables, and notes
  into concise findings.
- Generating alternative implementation approaches before Codex makes edits.
- Checking whether a proposed change stays inside the HPL sidecar scope.
- Producing research summaries that Claude can refine or Codex can implement.

Use Claude first when the core task is judgment-heavy project framing. Use Codex
first when the task is already ready for concrete edits, tests, or debugging.

## Exploration Rules

- Start by identifying the exact files and artifacts being compared.
- Prefer evidence from repository files and command output over assumptions.
- Keep source paths visible in summaries so another agent can follow up.
- Distinguish generated experiment artifacts from sidecar outputs created by
  this repository.
- Do not infer human preference labels from metrics, image quality scores, or
  optimization outputs.
- Flag uncertainty instead of filling gaps with invented data.

## Output Style

- Summarize broad findings first, then list supporting evidence by file.
- Group recommendations as `ready for Codex`, `needs Claude judgment`, or
  `needs user decision` when that helps routing.
- Include concrete next commands or files only when they follow directly from
  the evidence.
- Keep final handoffs concise enough for Codex to implement without redoing the
  entire scan.

## Boundaries To Preserve

- The sibling StringArtio repository is read-only by default.
- This lab does not automatically rerun generator experiments.
- This lab does not run a closed training loop.
- This lab does not implement RL unless the user explicitly changes scope.
- Optimization suggestions remain future candidate configs, not executed
  results.
