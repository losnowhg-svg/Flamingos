"""Compatibility wrapper. Both templates now share studio_ui.py."""
from library import show_library
from studio_ui import show_studio


def show_matchday(root):
    library = show_library()
    if library is not None:
        show_studio(root,'Matchday Screen',library)
