from __future__ import annotations

import argparse
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_INTERACTIVE_HELP = (
    "Choose where to write the block:\n"
    "  [a] AGENTS.md only\n"
    "  [c] CLAUDE.md only\n"
    "  [b] both AGENTS.md and CLAUDE.md\n"
    "  [s] skip (do nothing)\n"
)


class Command(BaseCommand):
    help = (
        "Add a static agent-help block to AGENTS.md and/or CLAUDE.md so coding agents "
        "(Claude Code, Cursor, Aider, Codex…) can use this dev server's autologin "
        "and dotfile-published endpoints without further instructions."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--target",
            action="append",
            default=[],
            dest="targets",
            metavar="FILENAME",
            help=(
                "Target filename relative to the project root (e.g. AGENTS.md, CLAUDE.md). "
                "May be repeated. Must be one of the names listed in DJANGO_DEV_HELPERS"
                "['claude_md']['files']. Defaults to all of those that already exist; "
                "if none exist, prompts interactively (or creates AGENTS.md in "
                "--non-interactive mode)."
            ),
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            dest="non_interactive",
            help="Never prompt. Use --target if given, otherwise create AGENTS.md.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="If an existing block (between markers) is found, replace it.",
        )

    def handle(self, *args, **options) -> None:
        from django_dev_helpers import project_root, prompt
        from django_dev_helpers.conf import get_config

        cfg = get_config()
        if cfg.claude_md.mode == "off":
            self.stderr.write(
                self.style.NOTICE(
                    "claude_md.mode is 'off' — proceeding anyway since you explicitly invoked this command."
                )
            )

        root = project_root.resolve_project_root(cfg)
        configured_files: list[str] = list(cfg.claude_md.files)

        explicit_targets: list[str] = list(options["targets"])
        for t in explicit_targets:
            if t not in configured_files:
                raise CommandError(
                    f"--target {t!r} is not in DJANGO_DEV_HELPERS['claude_md']['files']={configured_files!r}. "
                    "Add it to that setting first, or pass a different filename."
                )

        targets = self._resolve_targets(
            explicit=explicit_targets,
            configured=configured_files,
            root=root,
            non_interactive=options["non_interactive"],
        )

        if not targets:
            self.stdout.write(self.style.NOTICE("Nothing to do."))
            return

        block = prompt.render_static_agent_help_block(cfg)
        start_marker = cfg.claude_md.marker
        end_marker = prompt.derive_end_marker(start_marker)

        seen_resolved: set[Path] = set()
        for filename in targets:
            target_path = root / filename
            if target_path.is_symlink():
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipping {filename}: it is a symlink. "
                        "Edit the link target directly, or pass --target on the real file."
                    )
                )
                continue

            try:
                resolved = target_path.resolve(strict=False)
            except OSError:
                logger.exception("django-dev-helpers: cannot resolve %s", target_path)
                resolved = target_path
            if resolved in seen_resolved:
                self.stdout.write(f"Skipping {filename}: same file as a previous target.")
                continue
            seen_resolved.add(resolved)

            self._apply_to_file(
                target_path=target_path,
                block=block,
                start_marker=start_marker,
                end_marker=end_marker,
                force=options["force"],
            )

    def _resolve_targets(
        self,
        explicit: list[str],
        configured: list[str],
        root: Path,
        non_interactive: bool,
    ) -> list[str]:
        if explicit:
            seen: set[str] = set()
            ordered: list[str] = []
            for name in explicit:
                if name not in seen:
                    seen.add(name)
                    ordered.append(name)
            return ordered

        existing = [name for name in configured if (root / name).is_file()]
        if existing:
            return existing

        if non_interactive:
            if "AGENTS.md" in configured:
                default = "AGENTS.md"
            elif configured:
                default = configured[0]
            else:
                default = "AGENTS.md"
            self.stdout.write(f"No agent-help files found in {root}; creating {default} (--non-interactive).")
            return [default]

        return self._prompt_for_targets(configured, root)

    def _prompt_for_targets(self, configured: list[str], root: Path) -> list[str]:
        self.stdout.write(f"\nNeither AGENTS.md nor CLAUDE.md exists in {root}.\n{_INTERACTIVE_HELP}")
        while True:
            try:
                raw = input("Your choice [a/c/b/s]: ").strip().lower()
            except EOFError as exc:
                raise CommandError(
                    "Cannot prompt: stdin is not a TTY. Pass --non-interactive (and optionally --target) instead."
                ) from exc

            if raw in ("a", "agents", "agents.md"):
                return ["AGENTS.md"] if "AGENTS.md" in configured else [configured[0]]
            if raw in ("c", "claude", "claude.md"):
                return ["CLAUDE.md"] if "CLAUDE.md" in configured else [configured[0]]
            if raw in ("b", "both"):
                both = [n for n in ("AGENTS.md", "CLAUDE.md") if n in configured]
                return both or list(configured[:2])
            if raw in ("s", "skip", "n", "no", ""):
                return []
            self.stdout.write("Please answer with one of: a, c, b, s.")

    def _apply_to_file(
        self,
        target_path: Path,
        block: str,
        start_marker: str,
        end_marker: str,
        force: bool,
    ) -> None:
        filename = target_path.name

        if not target_path.exists():
            target_path.write_text(block, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Created {filename} with agent-help block."))
            return

        try:
            content = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CommandError(f"Cannot read {target_path}: {exc}") from exc

        if start_marker not in content:
            new_content = _append_block(content, block)
            target_path.write_text(new_content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Appended agent-help block to {filename}."))
            return

        if not force:
            self.stdout.write(
                f"Skipping {filename}: marker already present. Pass --force to replace the block in place."
            )
            return

        new_content = _replace_block(content, block, start_marker, end_marker)
        target_path.write_text(new_content, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Replaced existing agent-help block in {filename}."))


def _append_block(existing: str, block: str) -> str:
    if not existing:
        return block
    if existing.endswith("\n\n"):
        separator = ""
    elif existing.endswith("\n"):
        separator = "\n"
    else:
        separator = "\n\n"
    return f"{existing}{separator}{block}"


def _replace_block(content: str, block: str, start_marker: str, end_marker: str) -> str:
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return _append_block(content, block)

    end_search_from = start_idx + len(start_marker)
    end_idx = content.find(end_marker, end_search_from)
    if end_idx == -1:
        # Legacy block (no paired end marker): replace from start_marker to EOF.
        before = content[:start_idx].rstrip("\n")
        prefix = f"{before}\n\n" if before else ""
        return f"{prefix}{block}"

    end_idx += len(end_marker)
    before = content[:start_idx].rstrip("\n")
    after = content[end_idx:].lstrip("\n")
    prefix = f"{before}\n\n" if before else ""
    suffix = f"\n{after}" if after else "\n"
    return f"{prefix}{block.rstrip()}{suffix}"
