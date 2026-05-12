from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


_DJANGO_FLAG_NO_VALUE = frozenset(
    {
        "--version",
        "--traceback",
        "--no-color",
        "--force-color",
        "--skip-checks",
    }
)
_DJANGO_FLAG_TAKES_VALUE = frozenset(
    {
        "-v",
        "--verbosity",
        "--settings",
        "--pythonpath",
    }
)


class Command(BaseCommand):
    help = "Run `run-site run` (the run-site dev-stack orchestrator) with django-dev-helpers conveniences."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "run_site_args",
            nargs=argparse.REMAINDER,
            help="Arguments forwarded verbatim to `run-site run` (e.g. `--port 9000`).",
        )

    def run_from_argv(self, argv: list[str]) -> None:
        """Split argv so users don't need to type ``--`` before run-site flags.

        Django's default ``parse_args(argv[2:])`` rejects unknown options, so
        ``manage.py run_site --port 9000`` would error unless the user inserted
        ``--``. We pre-split argv into (Django flags, forwarded args) and
        rebuild it with an explicit ``--`` separator, so argparse's REMAINDER
        positional captures the forwarded args in their original order.
        """
        django_args, forwarded = _split_argv_for_run_site(list(argv[2:]))
        new_argv = list(argv[:2]) + django_args
        if forwarded:
            new_argv.append("--")
            new_argv.extend(forwarded)
        super().run_from_argv(new_argv)

    def handle(self, *args, **options) -> None:
        from django_dev_helpers.conf import get_config

        cfg = get_config()

        forwarded = list(options.get("run_site_args") or [])
        if forwarded and forwarded[0] == "--":
            forwarded = forwarded[1:]

        self._maybe_suggest_agent_help_block(cfg)

        # When invoked through a specific manage.py (e.g. `python
        # example_grappelli/manage.py run_site`), tell run-site to use that
        # exact manage.py rather than re-discovering and failing on projects
        # that ship multiple manage.py files.
        manage_py = _detect_invoking_manage_py()
        if manage_py and not _forwarded_has_arg(forwarded, "--manage-py"):
            forwarded = ["--manage-py", manage_py, *forwarded]

        # If we're already running inside `uv run`, pin run-site to the
        # current interpreter. Otherwise run-site's discovery may shell out
        # to a fresh `uv run python`, which — lacking the `--extra` flags
        # the user passed to the outer `uv run` — would re-sync the project
        # venv and remove those optional dependencies.
        if _is_running_under_uv() and not _forwarded_has_arg(forwarded, "--python"):
            forwarded = ["--python", sys.executable, *forwarded]

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
            logger.exception("django-dev-helpers: failed to render agent prompt for run_site suggestion")
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
            self.style.NOTICE("Silence globally with: DJANGO_DEV_HELPERS = {'claude_md': {'mode': 'off'}}.\n")
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


def _is_running_under_uv() -> bool:
    """Return True if the current process was launched via ``uv run``.

    ``uv run`` exports ``UV`` (the absolute path of the uv binary it used)
    into the child process; that env var is absent for plain ``python`` or
    activated-venv invocations, which makes it the most reliable signal.
    """
    return bool(os.environ.get("UV"))


def _detect_invoking_manage_py() -> str | None:
    """Return the absolute path of the manage.py used to invoke us, or None."""
    script = sys.argv[0] if sys.argv else ""
    if not script or os.path.basename(script) != "manage.py":
        return None
    abspath = os.path.abspath(script)
    if not os.path.isfile(abspath):
        return None
    return abspath


def _forwarded_has_arg(argv: list[str], name: str) -> bool:
    """Return True if ``name`` or ``name=...`` is already present in argv."""
    prefix = f"{name}="
    return any(a == name or a.startswith(prefix) for a in argv)


def _split_argv_for_run_site(args: list[str]) -> tuple[list[str], list[str]]:
    """Split manage.py args into (Django flags, args to forward to run-site).

    Anything that isn't one of Django's BaseCommand flags is forwarded. A
    literal ``--`` token still forces everything after it to be forwarded,
    so old invocations keep working.
    """
    django_args: list[str] = []
    forwarded: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            forwarded.extend(args[i + 1 :])
            break
        if a in _DJANGO_FLAG_NO_VALUE:
            django_args.append(a)
            i += 1
            continue
        if a in _DJANGO_FLAG_TAKES_VALUE:
            django_args.append(a)
            if i + 1 < len(args):
                django_args.append(args[i + 1])
                i += 2
            else:
                i += 1
            continue
        if "=" in a:
            opt = a.split("=", 1)[0]
            if opt in _DJANGO_FLAG_TAKES_VALUE or opt in _DJANGO_FLAG_NO_VALUE:
                django_args.append(a)
                i += 1
                continue
        # Short option with attached value, e.g. ``-v2``.
        if len(a) == 3 and a.startswith("-v") and a[2].isdigit():
            django_args.append(a)
            i += 1
            continue
        forwarded.append(a)
        i += 1
    return django_args, forwarded
