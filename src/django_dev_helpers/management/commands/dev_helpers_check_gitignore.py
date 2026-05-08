import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check that dev-helpers dotfiles are in .gitignore"

    def handle(self, *args, **options):
        from django_dev_helpers.conf import get_config

        cfg = get_config()
        if not cfg.is_active():
            self.stderr.write(
                "django-dev-helpers is not active; set DJANGO_DEV_HELPERS_ENABLED=1"
            )
            sys.exit(1)

        from django_dev_helpers.gitignore import get_gitignore_path, get_missing_entries

        gitignore_path = get_gitignore_path(cfg)
        if not gitignore_path.exists():
            self.stderr.write(f".gitignore not found at {gitignore_path}")
            sys.exit(1)

        content = gitignore_path.read_text()
        missing = get_missing_entries(content)
        if missing:
            self.stderr.write(f"Missing .gitignore entries: {', '.join(missing)}")
            sys.exit(1)

        self.stdout.write("All dev-helpers dotfiles are in .gitignore ✓")
