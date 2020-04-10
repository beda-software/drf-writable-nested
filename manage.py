#!/usr/bin/env python3

"""Django's command-line utility for administrative tasks.

This script is needed to recreate test Model migrations. To do that:

$ python manage.py makemigrations tests

This is needed in Django 2.2+ because the test Models have ForeignKeys
to Models outside of this app.
"""

import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
