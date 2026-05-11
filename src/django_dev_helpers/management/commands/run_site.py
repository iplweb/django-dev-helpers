from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run `run-site run` (the run-site dev-stack orchestrator) with django-dev-helpers conveniences."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "run_site_args",
            nargs=argparse.REMAINDER,
            help="Arguments forwarded verbatim to `run-site run` (use `-- --port 9000`).",
        )

    def handle(self, *args, **options) -> None:
        from django_dev_helpers.conf import get_config

        cfg = get_config()

        forwarded = list(options.get("run_site_args") or [])
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]

        self._maybe_suggest_agent_help_block(cfg)

        spawn_run_site(["run", *forwarded])

    def _maybe_suggest_agent_help_block(self, cfg) -> None:
        if cfg.claude_md.mode == "off":
            return

        from django_dev_helpers import project_root, prompt

        root = project_root.resolve_project_root(cfg)
        files = list(cfg.claude_md.files)
        marker = cfg.claude_md.marker

        existing = []
        for fname in files:
            p = root / fname
            if not p.is_file():
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                logger.exception("django-dev-helpers: cannot read %s", p)
                continue
            if marker in content:
                return
            existing.append(p.name)

        target_label = " or ".join(existing or files)

        # Use the *static* block (dotfile-referencing) rather than the
        # runtime banner. The static version is what should actually land
        # in AGENTS.md / CLAUDE.md: it sources port and endpoints from
        # ``$(cat .dev_helpers_*)`` so it does not go stale when the next
        # run picks a different free port. It also already includes the
        # paired markers — no manual marker line needed.
        try:
            rendered = prompt.render_static_agent_help_block(cfg)
        except Exception:
            logger.exception(
                "django-dev-helpers: failed to render agent prompt for run_site suggestion"
            )
            return

        self.stderr.write(
            self.style.NOTICE(
                f"\n[dev-helpers] Tip: paste the block below into {target_label} so coding "
                "agents can use this dev server without further instructions.\n"
                "Keep the marker line so this hint stays silent on subsequent runs.\n"
            )
        )
        self.stderr.write("--- 8< -------------------------------------------------------------")
        self.stderr.write(rendered)
        self.stderr.write("--- >8 -------------------------------------------------------------")
        self.stderr.write(
            self.style.NOTICE(
                "Silence globally with: DJANGO_DEV_HELPERS = {'claude_md': {'mode': 'off'}}.\n"
            )
        )


def spawn_run_site(argv: list[str]) -> None:
    """Replace the current process with `run-site <argv>`.

    Factored out so tests can patch it; in production this never returns.
    """
    binary = shutil.which("run-site")
    if binary is None:
        raise CommandError(
            "run-site is not installed.\n"
            "Install it as a uv tool:  uv tool install run-site\n"
            "Or in your project venv:  uv add --dev run-site"
        )
    os.execvp(binary, [binary, *argv])
    sys.exit(0)
