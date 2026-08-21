---
name: project-skill-router
description: >-
  Routes work to this repository's canonical Agent Skills under `.agents/skills/`.
  Use when the user invokes $decide-and-deliver or $decision-journal, asks to
  work in their personal decision-and-delivery style, pastes another Agent's
  answer for action-focused synthesis or a second opinion, or asks to record,
  review, list, or summarize a consequential decision. Also use when a project
  adds further canonical Skills under the same directory. Do not use for work
  that matches none of the canonical Skills.
---

# Canonical project Skill router

The authoritative workflows live under `../../../.agents/skills/`.
This router contains no workflow body.

1. Compare the current task with the `name` and `description` frontmatter in
   each canonical `*/SKILL.md`.
2. Select the smallest matching set.
3. Read every selected canonical `SKILL.md` completely before acting.
4. Resolve scripts, references, and assets relative to the selected canonical
   Skill directory — that directory is `{SKILL_DIR}` for those workflows.
5. Follow the canonical instructions exactly. Never copy a fix, a new rule, or
   a workflow step into this router; drift between the router and the canonical
   body is what `scripts/validate_agent_system.py` rejects.

Explicit Claude Code commands for the same workflows live in `.claude/commands/`.
