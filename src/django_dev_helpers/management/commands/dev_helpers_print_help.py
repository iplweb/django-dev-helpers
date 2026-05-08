import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Print agent help / prompt template for LLM sessions"

    def handle(self, *args, **options):
        from django_dev_helpers.conf import get_config

        cfg = get_config()
        if not cfg.is_active():
            self.stderr.write(
                "django-dev-helpers is not active; set DJANGO_DEV_HELPERS_ENABLED=1"
            )
            sys.exit(1)

        from django_dev_helpers.prompt import render_template

        self.stdout.write(render_template(cfg))
