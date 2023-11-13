"""
Settings for running scripts in /scripts
"""
import os
from os.path import abspath, dirname, join

if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error,wildcard-import
