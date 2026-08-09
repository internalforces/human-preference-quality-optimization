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
