#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
from app_common_python import LoadedConfig


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'python_starter.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?") from exc

    # Should not be none since we're using Clowder
    assert LoadedConfig is not None

    # Under the hood, execute_from_command_line() calls ManagementUtility() with
    # the arguments, but can just pass the arguments we want directly
    # first, let's make sure everything's migrated so django doesn't complain
    execute_from_command_line(["manage.py", "migrate"])
    port = LoadedConfig.publicPort
    args = ["manage.py", "runserver", f"0:{port}"]
    execute_from_command_line(args)



if __name__ == '__main__':
    main()
