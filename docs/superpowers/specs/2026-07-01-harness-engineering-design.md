# AI Development Harness Engineering — Design Spec

**Date:** 2026-07-01  
**Status:** Approved — v3 (2026-07-01)  
**Approach:** Flat augmentation (Approach A)

---

## Overview

This spec defines the AI Development Harness for the StringArtio Preference Lab. The harness transforms the repository into a structured operating system for long-term, multi-agent development. It reduces context loss across AI sessions, separates rules from operational references, and provides consistent workflows for Claude, Codex, Gemini, and future agents.

The harness extends what already exists rather than replacing it. `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `GEMINI.md`, and `docs/` remain in place. New directories (`memory/`, `tasks/`, `reports/`, `prompts/`) and files (`commands.md`, `ORCHESTRATOR.md`) are added at the repository root.

---

## Section 1 — Root-level Files

### `AGENTS.md` (modified)

Remains the project constitution: scope, hard boundaries, agent routing, preference data rules, modeling constraints, approval gates. The `## Development Commands` section is removed and replaced with a two-line pointer to `commands.md`. No other changes.

### `commands.md` (new)

Single source of truth for all execution commands. Organized by workflow stage:

1. Setup and validation
2. Lint and format
3. Test
4. Pipeline steps (ingest → features → queue → validate-preferences → train-model → suggest)
5. Dry-run pipeline
6. Benchmark and export
7. Release

Each command includes a one-line purpose annotation. Copy-paste ready. Updated here when commands change; `AGENTS.md` is not touched for command changes.

### `ORCHESTRATOR.md` (new)

Defines standard multi-agent workflows. Current role: human-guided orchestration — a human reads this and delegates to agents manually. Future role: compatible with automated orchestration without restructuring.

Three named workflows:

**Feature workflow:**
Human request → Claude (requirement analysis, scope check) → Human approval gate → Codex (implementation, tests) → Claude (review) → Gemini (alternatives, research) → Human final approval

**BugFix workflow:**
Human report → Claude (framing, risk) → Codex (debug, fix, test) → Claude (review) → Human approval

**Research workflow:**
Human question → Gemini (broad scan, synthesis) → Claude (judgment, recommendation) → Human decision

**Human approval gates** are required before:
- Modifying the main StringArtio app or its generated artifacts
- Deleting or overwriting data files
- Schema changes to `preferences.jsonl` or `candidate_manifest.json`
- Changes to model training strategy or optimizer constraints
- Release preparation

The ORCHESTRATOR.md makes the distinction explicit: workflows describe responsibilities, not automation. Agent names are role labels, not model names, so they remain valid if models change.

---

## Section 2 — `memory/`

Provides cross-session persistence. Separates current working context (rolling) from long-term records (append-only or immutable).

### `memory/project.md`

Static project identity. What this repo is, what it owns (steps 1–7 of the HPL loop), what is out of scope (generator reruns, closed-loop automation, RL), and which agents exist with their roles. Changes only when project scope changes. AI agents read this first to orient.

### `memory/architecture.md`

Concise, agent-oriented architectural briefing. Not a duplicate of `docs/architecture.md` — this is a compressed summary: pipeline stages, key data files, constraint system, boundary with sibling StringArtio repo. `docs/architecture.md` remains the authoritative detail reference.

### `memory/decisions.md`

Append-preferred log of significant architectural and design decisions. Each entry: date, decision, rationale, alternatives considered. Historical entries' meaning is never changed. Minor editorial corrections (typos, formatting, broken links) are acceptable. Written after a decision is made; never rewritten retroactively to reflect hindsight.

### `memory/known-issues.md`

Running list of unresolved issues, known limitations, and deferred work. Updated as issues are discovered or resolved. Distinct from `tasks/`: known-issues holds unscheduled problems. When an issue gets prioritized, it moves to `tasks/backlog.md`.

### `memory/glossary.md`

Stable project terminology definitions. Examples: HPL, Reward Model, Preference, Candidate, Source ID, Constraint, Pipeline Step, Blind Review, Both-Bad. Helps future AI agents maintain consistent terminology across sessions. Updated when new stable terms are introduced; definitions are not rewritten without a good reason.

### `memory/session.md`

Rolling current-state file. Continuously updated throughout a working session. Contains: current task, active owner, progress, blockers, next steps, and context an incoming agent needs to resume. At the end of a significant session, this file is archived as an immutable snapshot under `memory/sessions/`. Includes a header comment: "This file is overwritten each session. For history, see `memory/sessions/`."

### `memory/sessions/`

Immutable historical snapshots. Named `YYYY-MM-DD-brief-title.md`. Written at the end of a significant session. Never overwritten. Each snapshot contains: what was accomplished, decisions made, commands run, warnings observed, what comes next.

---

## Section 3 — `tasks/`

Scheduled, actionable work. Separate from `memory/known-issues.md`, which holds unscheduled problems.

### `tasks/active.md`

Current work in progress, organized by owner. One active task per owner (agent or human). Each entry: owner, task title, objective, priority, progress notes, blockers, next step. Multiple agents may have concurrent active tasks; each has its own entry.

### `tasks/backlog.md`

Ordered list of tasks not yet started. Each entry: title, objective, priority, owner, blocking dependencies, and an optional status field (Ready / Blocked / Waiting / Deferred). Agents pull from the top; humans reorder priorities.

### `tasks/completed.md`

Append-only log of finished tasks. Each entry: title, completion date, brief summary, and a link to the relevant session snapshot or milestone report when one exists. Small tasks are summarized here without a separate report.

---

## Section 4 — `reports/`

Milestone-only directory. Created only for significant work that would be valuable to revisit months later:

- Architecture changes
- New features
- Model training or evaluation runs
- Optimization cycles
- Dataset or schema changes
- Major refactoring
- Release preparation

Each report is a standalone file: `YYYY-MM-DD-brief-title.md`. No index file — the directory listing is the index. Small fixes, routine maintenance, and documentation updates are recorded only in `memory/session.md` and archived in `memory/sessions/`.

Each report contains: summary, files changed, commands run, tests executed, risks observed, validation outcome, next recommendation.

---

## Section 5 — `prompts/`

Reusable prompt templates. Primary consumer: humans starting a new AI session. Secondary consumer: a future orchestration system. Human-first, AI-compatible.

All five templates share a common header structure:

- **Objective** — what this session should accomplish
- **Context** — background an agent needs before starting
- **Relevant Files** — paths to read before acting
- **Constraints** — rules that must not be violated
- **Expected Output** — what the agent should produce
- **Validation** — how to verify the work is correct
- **Success Criteria** — definition of done

Role labels (Planner, Implementer, Reviewer, Researcher, Architect) replace model names so templates remain valid if underlying models change.

### `prompts/implementation.md`

For handing a scoped task to an implementation role (currently Codex). Additional sections: files to edit, test requirement, boundary conditions.

### `prompts/review.md`

For requesting a code or architecture review from a review role (currently Claude or Codex). Additional sections: what changed, what to look for, risk areas.

### `prompts/debug.md`

For investigating a failure or unexpected behavior. Additional sections: symptom, reproduction steps, what was already ruled out, suspected area.

### `prompts/research.md`

For broad exploration and synthesis (currently Gemini). Additional sections: question scope, files to scan, output format preference.

### `prompts/architecture.md`

For design and framing work (currently Claude). Additional sections: problem statement, design options to explore, what a good recommendation looks like.

---

## Naming Conventions

| Artifact | Pattern |
|----------|---------|
| Session snapshots | `memory/sessions/YYYY-MM-DD-brief-title.md` |
| Milestone reports | `reports/YYYY-MM-DD-brief-title.md` |
| Prompt templates | `prompts/<workflow>.md` (lowercase, no date) |
| Task files | `tasks/active.md`, `tasks/backlog.md`, `tasks/completed.md` |
| Spec files | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` |

---

## Section 6 — Agent Startup Order

When an AI agent starts a new session, it reads files in this order:

1. **`AGENTS.md`** — Establishes the project constitution: scope, hard boundaries, approval gates, routing rules. Everything that follows is subordinate to these rules.
2. **`memory/project.md`** — Orients the agent to the project identity: what is owned, what is out of scope, which agents exist. Faster to read than AGENTS.md for orientation; AGENTS.md has the authoritative rules.
3. **`memory/session.md`** — Loads current working state: active task, progress, blockers, next steps. This is where context from the previous session lives. Reading it before the agent-specific guide ensures the agent understands *what is happening* before learning *how it should act*.
4. **Agent-specific guide** (`CLAUDE.md` / `CODEX.md` / `GEMINI.md`) — Applies role-specific operating style and best-fit work guidance.
5. **`commands.md`** — Reference for execution commands. Read at startup so the agent can run pipeline steps without searching.
6. **Relevant `docs/`** — Deep reference files (architecture, data-flow, preference-schema) read on demand when the task requires them, not exhaustively at startup.
7. **Assigned task** — The specific entry from `tasks/active.md` or the human's request. Read last so all context is loaded before the task is interpreted.

**Why this order:** Rules before context, context before role, role before commands, commands before task. Each layer narrows the agent's operating frame so the assigned task is interpreted correctly rather than acted on with incomplete information.

---

## Section 7 — Ownership Matrix

Defines who is responsible for updating each operational file. Prevents ambiguity when multiple agents are active.

| File | Owner | When updated |
|------|-------|-------------|
| `AGENTS.md` | Human | Scope changes, boundary changes, approval gate changes |
| `commands.md` | Any agent or human | When commands change or new pipeline steps are added |
| `ORCHESTRATOR.md` | Human or Planner role | When workflows change or new agents are added |
| `memory/project.md` | Human | When project scope or agent roster changes |
| `memory/architecture.md` | Planner role (Claude) | After architecture decisions are approved |
| `memory/decisions.md` | Assigned agent | After any significant decision is made during a session |
| `memory/known-issues.md` | Any agent | When a new issue is discovered or an existing one is resolved |
| `memory/glossary.md` | Any agent | When a new stable term is introduced |
| `memory/session.md` | Assigned agent | Continuously throughout the session |
| `memory/sessions/` | Assigned agent | At the end of each significant session (immutable after creation) |
| `tasks/active.md` | Assigned agent | When task status, progress, or blockers change |
| `tasks/backlog.md` | Human or Planner role | When tasks are added, reordered, or promoted from known-issues |
| `tasks/completed.md` | Assigned agent | When a task is finished (append only) |
| `reports/` | Assigned agent | After milestone work only (see Section 4) |
| `prompts/` | Human or Planner role | When templates need refinement; not changed per-session |

**Owner definitions:**
- **Human** — only a human developer should make this change.
- **Planner role** — the agent acting in an architecture or planning capacity (currently Claude).
- **Assigned agent** — whichever agent owns the current task in `tasks/active.md`.
- **Any agent** — any agent may update this file as part of normal work.

---

## Section 8 — Update Trigger Rules

Explicit rules for when operational files must be updated. Agents should treat these as required steps, not optional cleanup.

| Trigger | Required updates |
|---------|-----------------|
| Session starts | Read `memory/session.md`; update `tasks/active.md` with current owner entry |
| Architecture decision approved | Append to `memory/decisions.md`; update `memory/architecture.md` if structure changes; create milestone report |
| Task completed (small) | Append to `tasks/completed.md`; update `memory/session.md` |
| Task completed (milestone) | Append to `tasks/completed.md`; create `reports/YYYY-MM-DD-title.md`; update `memory/session.md` |
| Bug discovered but not yet scheduled | Add to `memory/known-issues.md` |
| Known issue promoted to scheduled work | Move entry from `memory/known-issues.md` to `tasks/backlog.md` |
| New stable term introduced | Append to `memory/glossary.md` |
| Session ends (significant) | Archive `memory/session.md` to `memory/sessions/YYYY-MM-DD-title.md`; reset `memory/session.md` for next session |
| Schema or data format change | Create milestone report; update `docs/preference-schema.md` or `docs/data-flow.md` as appropriate |
| Agent roster or scope change | Human updates `AGENTS.md` and `memory/project.md` |
| Human approval gate triggered | Record in `memory/session.md`; do not proceed until approval is confirmed |

---

## Section 9 — Future Automation

The harness is intentionally human-guided today. This section documents how a future orchestration layer could operate without requiring structural changes to the repository.

**Current state:** A human reads `ORCHESTRATOR.md`, selects a workflow, and delegates steps to agents manually. Agents update memory and task files by convention.

**Future state (not yet implemented):** An orchestrator process could automate the following steps using the same files that exist today:

1. **Classify incoming work** — Parse the human's request and match it to a workflow in `ORCHESTRATOR.md` (Feature, BugFix, Research, or a custom extension).
2. **Select the appropriate role** — Use the agent routing table in `AGENTS.md` to assign the first step to the correct role.
3. **Assemble project context** — Follow the Agent Startup Order (Section 6) to build a context payload: rules, project identity, current session state, role guide, commands, relevant docs, task.
4. **Execute standardized prompt templates** — Fill in the relevant template from `prompts/` with the assembled context and task details, then dispatch to the assigned agent.
5. **Collect outputs** — Receive the agent's output, update `tasks/active.md` and `memory/session.md`, and route to the next step in the workflow.
6. **Trigger human approval gates** — Pause the workflow at defined gates (see Section 1) and wait for explicit human confirmation before continuing.
7. **Archive session memory** — At workflow completion, write the session snapshot to `memory/sessions/` and create a milestone report in `reports/` if applicable.

**Design compatibility:** No new files or directories are required for this future layer. The orchestrator reads and writes the same files humans use today. The prompt templates in `prompts/` are already structured for machine parsing (common header schema, bracketed variables). The ownership matrix (Section 7) and update trigger rules (Section 8) give an orchestrator enough information to maintain project state correctly without human guidance on every step.

---

## Section 10 — Work Lifecycle

Every piece of work passes through a defined sequence of stages. This gives all agents a shared vocabulary for where a task currently lives and what is expected at each stage.

```text
Idea → Known Issue → Backlog → Ready → Active → Review → Human Approval → Completed → Milestone Report → Session Archive
```

| Stage | Purpose | Entry condition | Exit condition | Files that change |
|-------|---------|----------------|---------------|-------------------|
| **Idea** | Capture a possibility before evaluating it | Any agent or human identifies something worth considering | Evaluated as worth tracking or discarded | `memory/session.md` (note only) |
| **Known Issue** | Track unscheduled problems and limitations | Idea is confirmed as real and worth preserving | Promoted to backlog or closed as won't-fix | `memory/known-issues.md` |
| **Backlog** | Queue of prioritized, actionable tasks | Human or Planner promotes issue; task is fully described | Human marks it Ready and assigns an owner | `tasks/backlog.md` |
| **Ready** | Task is assigned and can start immediately | Owner is identified; no blockers exist | Assigned agent picks it up | `tasks/backlog.md` (status → Ready) |
| **Active** | Work in progress | Assigned agent starts the task | Work is complete or blocked | `tasks/active.md`, `memory/session.md` |
| **Review** | Output is checked before closing | Agent completes implementation or research | Reviewer approves or requests changes | `memory/session.md`, relevant source files |
| **Human Approval** | Required gate for risky operations | Task touches an approval-gated area (see Section 1) | Human explicitly approves or rejects | `memory/session.md` (record decision) |
| **Completed** | Task is closed | Review passed; approval obtained if required | — | `tasks/completed.md`, `tasks/active.md` (entry removed) |
| **Milestone Report** | Durable record for significant work | Task qualifies as a milestone (see Section 4) | Report written | `reports/YYYY-MM-DD-title.md` |
| **Session Archive** | Immutable snapshot of session context | Significant session ends | — | `memory/sessions/YYYY-MM-DD-title.md`, `memory/session.md` (reset) |

Not every task passes through every stage. Small fixes go Backlog → Active → Completed. Large features traverse the full sequence including Review, Human Approval, Milestone Report, and Session Archive.

---

## Section 11 — Context Loading Strategy

As the repository grows, agents should load context selectively rather than reading every file on startup. The startup order in Section 6 defines the sequence; this section defines the scope.

**Always read at session start:**

- `AGENTS.md` — rules and boundaries that govern all decisions
- `memory/project.md` — project identity and scope
- `memory/session.md` — current working state

**Read when the task requires it:**

- `commands.md` — when about to run pipeline steps or need command syntax
- `docs/architecture.md`, `docs/data-flow.md`, `docs/preference-schema.md` — when the task touches pipeline structure, data formats, or modeling
- `memory/architecture.md` — when making or reviewing architectural decisions
- `memory/decisions.md` — when the task involves a design choice with relevant precedent
- `memory/known-issues.md` — when diagnosing a bug or evaluating scope
- `memory/glossary.md` — when terminology is ambiguous
- `tasks/backlog.md` — when planning or prioritizing next work
- `reports/` — when researching the history of a specific milestone

**Never load automatically:**

- `memory/sessions/` archives — load only a specific snapshot when explicitly relevant to the current task (e.g., "what did we decide on 2026-07-01?")
- Old `reports/` entries — same rule; load a specific report only when its content is relevant, not as background reading
- `prompts/` — load the specific template for the current workflow type; do not read the full directory

**Rationale:** The always-read set is small by design. An agent that reads everything on startup fills its context with information it may never use, crowding out task-relevant content. The on-demand rules preserve correctness: no agent should make an architectural decision without reading `memory/decisions.md`, but a routine pipeline debugging task does not need it.

---

## Section 12 — Future Repository Evolution

The current harness is deliberately minimal. Its flat structure and file-based conventions are compatible with future capabilities that do not exist yet. This section documents the intended evolution path so future additions do not require restructuring what is already here.

**Capabilities the current structure supports without change:**

- **Agent registry** — A future `agents.json` or `agents.md` could enumerate all agents, their role labels, model assignments, and capability tags. `AGENTS.md` already defines routing logic; a registry would make it machine-readable.
- **Role registry** — Role labels (Planner, Implementer, Reviewer, Researcher, Architect) are used throughout the spec. A role registry would formalize their capabilities, constraints, and handoff protocols.
- **Capability registry** — Agents could declare which pipeline steps, file types, and task categories they can handle. The orchestrator would use this to route work without hardcoding agent assignments.
- **Workflow catalog** — `ORCHESTRATOR.md` already defines three workflows. A machine-readable catalog would allow an orchestrator to select and compose workflows dynamically.
- **Orchestration runtime** — A process that executes the startup order (Section 6), fills prompt templates from `prompts/`, dispatches to agents, collects outputs, updates `memory/` and `tasks/` files, and triggers human approval gates. All inputs and outputs already exist as files.
- **Automated task routing** — Using the ownership matrix (Section 7), update trigger rules (Section 8), and work lifecycle (Section 10), an orchestrator could determine the correct next action for any task state without human intervention at each step.

**Design principle:** None of these future components require new directories or a change to the flat augmentation structure. They extend the existing files — `AGENTS.md`, `ORCHESTRATOR.md`, `prompts/`, `memory/`, `tasks/` — by making their conventions machine-readable. The repository evolves by deepening what exists, not by adding new layers.

---

## What Is Not Changing

- `docs/` remains the authoritative reference for stable project documentation.
- No separate `knowledge/` directory — `docs/` already covers this.
- `CLAUDE.md`, `CODEX.md`, `GEMINI.md` retain their agent-specific guidance.
- Hard boundaries in `AGENTS.md` (no generator reruns, no RL, no label fabrication) are not weakened.
- `data/` pipeline structure is unchanged.

---

## Files Created by This Spec

```text
commands.md
ORCHESTRATOR.md
memory/project.md
memory/architecture.md
memory/decisions.md
memory/known-issues.md
memory/glossary.md
memory/session.md
memory/sessions/        (empty directory, .gitkeep)
tasks/active.md
tasks/backlog.md
tasks/completed.md
reports/                (empty directory, .gitkeep)
prompts/implementation.md
prompts/review.md
prompts/debug.md
prompts/research.md
prompts/architecture.md
docs/superpowers/specs/ (this file)
```

`AGENTS.md` is modified: `## Development Commands` section replaced with a pointer to `commands.md`.
