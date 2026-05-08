"""Verify the autoreload contract by running real Python subprocesses.

The promise: when a parent process initialises DEV_HELPERS_AUTOLOGIN_TOKEN
and then re-execs (via Django's runserver autoreloader) into a child, the
child must see the same token. We exercise this by calling init_token in
a parent, exporting the env, and reading it from a child subprocess.
"""

import os
import subprocess
import sys
import textwrap


def test_token_persists_across_subprocess(tmp_path):
    parent_script = textwrap.dedent(
        """
        import os, sys
        sys.path.insert(0, %r)
        from django_dev_helpers.tokens import init_token
        token = init_token()
        print(token)
        """
    ) % os.path.join(os.path.dirname(__file__), "..", "src")

    parent = subprocess.run(
        [sys.executable, "-c", parent_script],
        check=True,
        capture_output=True,
        text=True,
    )
    parent_token = parent.stdout.strip()
    assert parent_token

    child_script = textwrap.dedent(
        """
        import os, sys
        sys.path.insert(0, %r)
        from django_dev_helpers.tokens import init_token
        token = init_token()
        print(token)
        """
    ) % os.path.join(os.path.dirname(__file__), "..", "src")

    env = os.environ.copy()
    env["DEV_HELPERS_AUTOLOGIN_TOKEN"] = parent_token
    child = subprocess.run(
        [sys.executable, "-c", child_script],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert child.stdout.strip() == parent_token


def test_token_freshly_generated_when_unset(tmp_path):
    script = textwrap.dedent(
        """
        import os, sys
        sys.path.insert(0, %r)
        os.environ.pop('DEV_HELPERS_AUTOLOGIN_TOKEN', None)
        from django_dev_helpers.tokens import init_token
        token = init_token()
        assert token
        assert len(token) >= 32
        print(token)
        """
    ) % os.path.join(os.path.dirname(__file__), "..", "src")

    env = os.environ.copy()
    env.pop("DEV_HELPERS_AUTOLOGIN_TOKEN", None)
    a = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, env=env)
    b = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, env=env)
    assert a.stdout.strip() != b.stdout.strip()
