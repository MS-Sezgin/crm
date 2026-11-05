"""Locations of the data, credentials and bundled resource folders.

Normal run:  folders are next to the source files.
.exe run:    data/ and credentials/ sit next to the .exe (user-editable),
             ui/ and assets/ are bundled inside the .exe (read-only).
"""
import os
import sys


def app_dir():
    """Folder that holds the user's data/ and credentials/ folders."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """Folder that holds the bundled ui/ and assets/ folders."""
    return getattr(sys, "_MEIPASS", app_dir())
