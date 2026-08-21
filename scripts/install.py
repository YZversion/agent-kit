#!/usr/bin/env python3
"""Install the cross-tool agent system into a project repository.

    python scripts/install.py <target-repo> [--dry-run] [--force]
    python scripts/install.py <target-repo> --tools claude,cursor

Copies the canonical `.agents/` layer plus the thin per-tool adapters, and
seeds `AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md` when the project has none.

Safety rules, in order of importance:

* Files the project already owns are never overwritten. Existing kit files with
  different content are reported as CONFLICT and skipped unless `--force`.
* Governance docs are seeded only when absent; an existing AGENTS.md is left
  alone because it holds project rules this kit knows nothing about.
* `.agents/skills/` is merged per Skill directory, so a project that already
  keeps its own Skills there (a platform template, for instance) keeps them.
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent

ALL_TOOLS = ("claude", "cursor", "opencode")

# Governance docs are seeded from templates only when the target has none.
SEED_DOCS = {
    "AGENTS.md": KIT / "docs" / "AGENTS.template.md",
    "CLAUDE.md": KIT / "docs" / "CLAUDE.template.md",
    "CONTRIBUTING.md": KIT / "docs" / "CONTRIBUTING.template.md",
}

GITIGNORE_BLOCK = """
# Agent scratch area: plans, logs, snapshots, decision ledger. Never tracked.
.agent-work/
"""


class Installer:
    def __init__(self, target: Path, dry_run: bool, force: bool) -> None:
        self.target = target
        self.dry_run = dry_run
        self.force = force
        self.copied: list[str] = []
        self.skipped: list[str] = []
        self.conflicts: list[str] = []

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.target)).replace("\\", "/")

    def copy_file(self, src: Path, dest: Path, *, seed_only: bool = False) -> None:
        """Copy one file, refusing to clobber content the project owns."""
        if dest.exists():
            if seed_only:
                self.skipped.append(f"{self.rel(dest)} (already exists, left alone)")
                return
            if filecmp.cmp(src, dest, shallow=False):
                self.skipped.append(f"{self.rel(dest)} (identical)")
                return
            if not self.force:
                self.conflicts.append(f"{self.rel(dest)} (differs; use --force to replace)")
                return
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        self.copied.append(self.rel(dest))

    def copy_tree(self, src_root: Path, dest_root: Path) -> None:
        for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
            if "__pycache__" in src.parts:
                continue
            self.copy_file(src, dest_root / src.relative_to(src_root))

    def install_canonical(self) -> None:
        """Merge `.agents/` per directory so project-owned Skills survive."""
        self.copy_tree(KIT / "agents" / "skills", self.target / ".agents" / "skills")
        self.copy_tree(KIT / "agents" / "templates", self.target / ".agents" / "templates")

    def install_claude(self) -> None:
        self.copy_tree(
            KIT / "adapters" / "claude" / "skills",
            self.target / ".claude" / "skills",
        )
        self.copy_tree(
            KIT / "adapters" / "claude" / "commands",
            self.target / ".claude" / "commands",
        )

    def install_cursor(self) -> None:
        self.copy_tree(
            KIT / "adapters" / "cursor" / "rules",
            self.target / ".cursor" / "rules",
        )

    def install_opencode(self) -> None:
        # opencode.json is a whole-project config; seeding it over an existing
        # one would silently drop the project's own instructions.
        self.copy_file(
            KIT / "adapters" / "opencode" / "opencode.json",
            self.target / "opencode.json",
            seed_only=True,
        )

    def install_validator(self) -> None:
        self.copy_file(
            KIT / "scripts" / "validate_agent_system.py",
            self.target / "scripts" / "validate_agent_system.py",
        )

    def seed_docs(self) -> None:
        for name, template in SEED_DOCS.items():
            self.copy_file(template, self.target / name, seed_only=True)

    def ensure_gitignore(self) -> None:
        gitignore = self.target / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
        if any(
            line.strip() in {".agent-work/", ".agent-work", "/.agent-work/"}
            for line in existing.splitlines()
        ):
            self.skipped.append(".gitignore (.agent-work/ already ignored)")
            return
        if not self.dry_run:
            with gitignore.open("a", encoding="utf-8") as handle:
                if existing and not existing.endswith("\n"):
                    handle.write("\n")
                handle.write(GITIGNORE_BLOCK)
        self.copied.append(".gitignore (appended .agent-work/)")

    def report(self) -> int:
        prefix = "[dry-run] " if self.dry_run else ""
        print(f"{prefix}installed into {self.target}\n")
        for label, items in (
            ("written", self.copied),
            ("skipped", self.skipped),
            ("CONFLICT", self.conflicts),
        ):
            if items:
                print(f"{label} ({len(items)}):")
                for item in items:
                    print(f"  {item}")
                print()
        if self.conflicts:
            print("Conflicts were left untouched. Review them, then re-run with --force")
            print("only for the ones you actually want the kit version of.")
            return 1
        print("Next: cd into the project and run")
        print("  python scripts/validate_agent_system.py")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", type=Path, help="path to the project repository")
    parser.add_argument(
        "--tools",
        default=",".join(ALL_TOOLS),
        help=f"comma-separated adapters to install (default: {','.join(ALL_TOOLS)})",
    )
    parser.add_argument("--dry-run", action="store_true", help="show actions, change nothing")
    parser.add_argument(
        "--force", action="store_true", help="replace kit files that differ"
    )
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    if not target.is_dir():
        print(f"error: target is not a directory: {target}", file=sys.stderr)
        return 2

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    unknown = sorted(set(tools) - set(ALL_TOOLS))
    if unknown:
        print(f"error: unknown tools: {', '.join(unknown)}", file=sys.stderr)
        return 2

    installer = Installer(target, args.dry_run, args.force)
    installer.install_canonical()
    if "claude" in tools:
        installer.install_claude()
    if "cursor" in tools:
        installer.install_cursor()
    if "opencode" in tools:
        installer.install_opencode()
    installer.install_validator()
    installer.seed_docs()
    installer.ensure_gitignore()
    return installer.report()


if __name__ == "__main__":
    sys.exit(main())
