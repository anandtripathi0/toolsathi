"""Copy into the actual WSGI file linked by the existing PythonAnywhere Web tab.

Inspect and preserve the platform file first. This is a template, not its path.
"""
import os
import sys

PROJECT = '/home/anandtrip22/toolsathi'
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from config.environment import load_environment

os.environ['TOOLSATHI_ENV_FILE'] = '/home/anandtrip22/.toolsathi.env'
load_environment(os.environ['TOOLSATHI_ENV_FILE'], override=True)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from config.wsgi import application
