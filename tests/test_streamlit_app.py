"""Optional real Streamlit widget tests. Components are not a browser here."""
import importlib.util
import unittest
from pathlib import Path
from studio_state import empty_library

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec('streamlit'),'Streamlit is not installed in this environment')
class StreamlitAppTests(unittest.TestCase):
    def test_four_editor_pages(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=90)
        app.session_state['studio_library']=empty_library()
        app.run()
        for template in ('Starting 7','Matchday Screen','Full Time','Convocati'):
            app.sidebar.radio[0].set_value(template).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual(app.session_state['studio_models'][template]['font_choice'],
                             'Sans Bold' if template=='Starting 7' else 'CRT Terminal')
