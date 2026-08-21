#!/usr/bin/env python3
"""Validate the cross-tool agent system in a consuming repository.

Enforces the single invariant the whole design rests on: `.agents/skills/`
holds the only workflow bodies, and every tool adapter is a thin pointer that
must not drift from it.

Run from the repository root:

    python scripts/validate_agent_system.py

Exit code 0 means every check passed. Any failure prints `FAIL <check>: reason`
and exits 1, so this is safe to wire into CI or a pre-commit hook.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CANONICAL_SKILLS = ROOT / ".agents" / "skills"
CLAUDE_COMMANDS = ROOT / ".claude" / "commands"
CLAUDE_ROUTER = ROOT / ".claude" / "skills" / "project-skill-router" / "SKILL.md"
CURSOR_RULE = ROOT / ".cursor" / "rules" / "cross-tool-contract.mdc"
OPENCODE_CONFIG = ROOT / "opencode.json"

# Entry docs every tool reads. CLAUDE.md is optional when another system owns
# one; the check only requires it to reference AGENTS.md when present.
REQUIRED_ENTRIES = ("AGENTS.md", "CONTRIBUTING.md")

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class CheckFailure(Exception):
    """A single validation failure carrying an actionable message."""


def read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def normalized(value: str) -> str:
    """Collapse whitespace so YAML folding never counts as drift."""
    return " ".join(value.split())


def frontmatter(text: str, label: str) -> dict[str, str]:
    match = FRONTMATTER.match(text)
    if not match:
        raise CheckFailure(f"{label}: missing YAML frontmatter")
    fields: dict[str, str] = {}
    key: str | None = None
    for raw in match.group(1).splitlines():
        if not raw.strip():
            continue
        header = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if header and not raw.startswith((" ", "\t")):
            key = header.group(1)
            value = header.group(2).strip()
            fields[key] = "" if value in (">-", ">", "|", "|-") else value
        elif key:
            fields[key] = (fields[key] + " " + raw.strip()).strip()
    return fields


def canonical_skills() -> dict[str, dict[str, str]]:
    if not CANONICAL_SKILLS.is_dir():
        raise CheckFailure(".agents/skills/ does not exist")
    found: dict[str, dict[str, str]] = {}
    for skill_md in sorted(CANONICAL_SKILLS.glob("*/SKILL.md")):
        label = str(skill_md.relative_to(ROOT))
        fields = frontmatter(read(skill_md), label)
        directory = skill_md.parent.name
        name = fields.get("name", "")
        if not name:
            raise CheckFailure(f"{label}: frontmatter has no name")
        if name != directory:
            raise CheckFailure(
                f"{label}: frontmatter name {name} does not match directory {directory}"
            )
        if not fields.get("description"):
            raise CheckFailure(f"{label}: frontmatter has no description")
        found[name] = fields
    if not found:
        raise CheckFailure(".agents/skills/ contains no */SKILL.md")
    return found


def check_entries() -> None:
    for entry in REQUIRED_ENTRIES:
        read(ROOT / entry)
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists() and "AGENTS.md" not in read(claude_md):
        raise CheckFailure("CLAUDE.md does not import or reference AGENTS.md")


def check_commands(skills: dict[str, dict[str, str]]) -> None:
    """Each kit-managed Claude command must not drift from its canonical Skill."""
    if not CLAUDE_COMMANDS.is_dir():
        raise CheckFailure(".claude/commands/ does not exist")
    checked = 0
    for command in sorted(CLAUDE_COMMANDS.glob("*.md")):
        name = command.stem
        # A project may keep unrelated commands; only ones named after a
        # canonical Skill are kit-managed and subject to the drift check.
        if name not in skills:
            continue
        label = str(command.relative_to(ROOT))
        text = read(command)
        fields = frontmatter(text, label)
        want = normalized(skills[name]["description"])
        got = normalized(fields.get("description", ""))
        if got != want:
            raise CheckFailure(
                f"{label}: description drifted from .agents/skills/{name}/SKILL.md"
            )
        pointer = f".agents/skills/{name}/SKILL.md"
        if pointer not in text:
            raise CheckFailure(f"{label}: body does not point at {pointer}")
        checked += 1
    if checked == 0:
        raise CheckFailure(
            ".claude/commands/ has no command matching a canonical Skill name"
        )


def check_router(skills: dict[str, dict[str, str]]) -> None:
    text = read(CLAUDE_ROUTER)
    frontmatter(text, str(CLAUDE_ROUTER.relative_to(ROOT)))
    if ".agents/skills" not in text:
        raise CheckFailure("project-skill-router does not point at .agents/skills/")
    # The router must stay a pointer. A canonical section copied into it is drift.
    for name in skills:
        body = read(CANONICAL_SKILLS / name / "SKILL.md")
        for heading in re.findall(r"^## (.+)$", body, re.MULTILINE):
            if f"## {heading}" in text:
                raise CheckFailure(
                    f"project-skill-router copied section '{heading}' "
                    f"from .agents/skills/{name}/SKILL.md"
                )


def check_opencode() -> None:
    if not OPENCODE_CONFIG.exists():
        return  # OpenCode support is optional per project.
    data = json.loads(read(OPENCODE_CONFIG))
    paths = data.get("skills", {}).get("paths", [])
    if ".agents/skills" not in paths:
        raise CheckFailure("opencode.json skills.paths does not include .agents/skills")


def check_cursor() -> None:
    if not CURSOR_RULE.exists():
        return  # Cursor support is optional per project.
    text = read(CURSOR_RULE)
    if "alwaysApply: true" not in text:
        raise CheckFailure("cross-tool-contract.mdc is not alwaysApply: true")
    if ".agents/skills" not in text:
        raise CheckFailure("cross-tool-contract.mdc does not point at .agents/skills/")


def check_local_state_boundary() -> None:
    """.agent-work/ is the scratch area and must never be tracked."""
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        raise CheckFailure("missing .gitignore; .agent-work/ would be committed")
    entries = {line.strip() for line in read(gitignore).splitlines()}
    if not entries & {".agent-work/", ".agent-work", "/.agent-work/"}:
        raise CheckFailure(".gitignore does not ignore .agent-work/")


SIMPLE_CHECKS = (
    ("entries", check_entries),
    ("local-state-boundary", check_local_state_boundary),
    ("opencode", check_opencode),
    ("cursor", check_cursor),
)

SKILL_CHECKS = (
    ("claude-commands", check_commands),
    ("claude-router", check_router),
)


def main() -> int:
    try:
        skills = canonical_skills()
    except CheckFailure as exc:
        print(f"FAIL canonical-skills: {exc}")
        return 1
    print(f"PASS canonical-skills: {', '.join(sorted(skills))}")

    failures: list[str] = []
    for name, check in SIMPLE_CHECKS:
        try:
            check()
        except CheckFailure as exc:
            failures.append(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")

    for name, skill_check in SKILL_CHECKS:
        try:
            skill_check(skills)
        except CheckFailure as exc:
            failures.append(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")

    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
