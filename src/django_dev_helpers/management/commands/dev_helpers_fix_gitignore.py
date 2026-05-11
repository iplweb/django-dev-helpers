from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Add django-dev-helpers runtime dotfiles to .gitignore. "
        "Idempotent — entries already present are left alone. "
        "Use this when you've seen the 'missing entries from .gitignore' warning "
        "and want to fix it without flipping the global gitignore.mode to 'auto-add'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=("Report which entries would be added and exit. Does not modify .gitignore."),
        )

    def handle(self, *args, **options):
        from django_dev_helpers.conf import get_config
        from django_dev_helpers.gitignore import (
            get_gitignore_path,
            get_missing_entries,
        )

        cfg = get_config()
        gitignore_path = get_gitignore_path(cfg)
        existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
        missing = get_missing_entries(existing, cfg)

        if not missing:
            target = gitignore_path if gitignore_path.exists() else f"{gitignore_path} (new)"
            self.stdout.write(f"All dev-helpers dotfile entries already present in {target}.")
            return

        if options["dry_run"]:
            self.stdout.write(
                f"Would add {len(missing)} entr"
                f"{'y' if len(missing) == 1 else 'ies'} to {gitignore_path} "
                "(dry run, nothing written):"
            )
            for entry in missing:
                self.stdout.write(f"  + {entry}")
            return

        # Append-only — never rewrite or reorder existing content. A header
        # comment tags the lines with the tool name so a future reader
        # knows what owns them. If the file did not exist yet, ``open(...,
        # "a")`` creates it.
        header = "# django-dev-helpers"
        block = [header, *missing]
        with open(gitignore_path, "a", encoding="utf-8") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(block) + "\n")

        verb = "entry" if len(missing) == 1 else "entries"
        self.stdout.write(f"Added {len(missing)} {verb} to {gitignore_path}:")
        for entry in missing:
            self.stdout.write(f"  + {entry}")
