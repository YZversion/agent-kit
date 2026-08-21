#!/usr/bin/env python3
"""Install the generic Skills into the user-level Claude Code config.

    python scripts/install_global.py [--dry-run] [--force] [--home <dir>]

Copies every canonical Skill under `agents/skills/` into `~/.claude/skills/`
and writes matching `~/.claude/commands/` entries. Skills installed there load
in every project with no per-project files at all, which is the point: you stop
copying this kit around just to get `$decide-and-deliver`.

The command bodies differ from the project adapters on purpose. A project
install points at `.agents/skills/<name>/SKILL.md`; that path does not exist
for a global install, so the global command refers to the Skill by name.
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
CANONICAL = KIT / "agents" / "skills"

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

COMMAND_TEMPLATE = """---
{frontmatter}
---

Load the `{name}` Skill and follow it completely as the authoritative workflow.
Resolve its scripts, references, and assets relative to that Skill's own
directory, which the loader reports as its base directory.
"""


def description_block(skill_md: Path) -> str:
    """Reuse the canonical description verbatim so the two never drift."""
    text = skill_md.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        raise SystemExit(f"error: {skill_md} has no frontmatter")
    lines = match.group(1).splitlines()
    kept: list[str] = []
    capturing = False
    for line in lines:
        if line.startswith("description:"):
            capturing = True
            kept.append(line)
            continue
        if capturing:
            # Continuation lines of a folded scalar are indented.
            if line.startswith((" ", "\t")) or not line.strip():
                kept.append(line)
                continue
            break
    if not kept:
        raise SystemExit(f"error: {skill_md} has no description")
    return "\n".join(kept).rstrip()


class GlobalInstaller:
    def __init__(self, home: Path, dry_run: bool, force: bool) -> None:
        self.skills_root = home / ".claude" / "skills"
        self.commands_root = home / ".claude" / "commands"
        self.dry_run = dry_run
        self.force = force
        self.written: list[str] = []
        self.skipped: list[str] = []
        self.conflicts: list[str] = []

    def put(self, dest: Path, src: Path | None = None, content: str | None = None) -> None:
        label = str(dest)
        if dest.exists():
            same = (
                filecmp.cmp(src, dest, shallow=False)
                if src is not None
                else dest.read_text(encoding="utf-8") == content
            )
            if same:
                self.skipped.append(f"{label} (identical)")
                return
            if not self.force:
                self.conflicts.append(f"{label} (differs; use --force to replace)")
                return
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src is not None:
                shutil.copy2(src, dest)
            else:
                dest.write_text(content or "", encoding="utf-8", newline="\n")
        self.written.append(label)

    def install(self) -> int:
        skills = sorted(p.parent for p in CANONICAL.glob("*/SKILL.md"))
        if not skills:
            print("error: no canonical Skills found", file=sys.stderr)
            return 2

        for skill_dir in skills:
            name = skill_dir.name
            for src in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
                if "__pycache__" in src.parts:
                    continue
                self.put(
                    self.skills_root / name / src.relative_to(skill_dir), src=src
                )
            self.put(
                self.commands_root / f"{name}.md",
                content=COMMAND_TEMPLATE.format(
                    frontmatter=description_block(skill_dir / "SKILL.md"),
                    name=name,
                ),
            )

        prefix = "[dry-run] " if self.dry_run else ""
        print(f"{prefix}global install -> {self.skills_root.parent}\n")
        for label, items in (
            ("written", self.written),
            ("skipped", self.skipped),
            ("CONFLICT", self.conflicts),
        ):
            if items:
                print(f"{label} ({len(items)}):")
                for item in items:
                    print(f"  {item}")
                print()
        if self.conflicts:
            print("Conflicts left untouched. Re-run with --force only for the ones")
            print("you want the kit version of.")
            return 1
        print("Restart Claude Code so it rediscovers user-level Skills.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show actions, change nothing")
    parser.add_argument("--force", action="store_true", help="replace files that differ")
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="override the home directory (for testing)",
    )
    args = parser.parse_args()
    return GlobalInstaller(args.home.expanduser().resolve(), args.dry_run, args.force).install()


if __name__ == "__main__":
    sys.exit(main())
