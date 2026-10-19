#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    from config.environment import load_configured_environment
    load_configured_environment()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
