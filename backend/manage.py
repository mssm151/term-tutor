#!/usr/bin/env python
"""Management entry point for the Django scaffold."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is unavailable. Install requirements.txt with your Conda interpreter."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
