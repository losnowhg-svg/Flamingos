"""3.6: phone experience - share sheet helper, menu and preview wiring."""
import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import share


class Share(unittest.TestCase):
    def test_carousel_from_zip_in_order(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('02_difensori.png', b'b')
            archive.writestr('01_convocati.png', b'a')
            archive.writestr('note.txt', b'x')
        files = share.from_zip(buffer.getvalue())
        self.assertEqual([name for _, name, _ in files], ['01_convocati.png', '02_difensori.png'])
        self.assertTrue(all(kind == 'image/png' for _, _, kind in files))

    def test_too_big_or_empty_shows_nothing(self):
        import types
        calls = []
        comp = types.ModuleType('streamlit.components.v1')
        comp.html = lambda html, height=0: calls.append(html)
        saved = {k: sys.modules.get(k) for k in ('streamlit', 'streamlit.components', 'streamlit.components.v1')}
        sys.modules['streamlit'] = sys.modules.get('streamlit') or types.ModuleType('streamlit')
        sys.modules['streamlit.components'] = types.ModuleType('streamlit.components')
        sys.modules['streamlit.components.v1'] = comp
        try:
            share.button(b'', 'a.png', 'image/png')
            share.button(b'x'*(share.LIMIT+1), 'a.mp4', 'video/mp4')
            self.assertEqual(calls, [])
            share.button(b'png', 'a.png', 'image/png')
            self.assertEqual(len(calls), 1)
            self.assertIn('navigator.canShare', calls[0])
            self.assertIn('"a.png"', calls[0])
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


class PhoneLayout(unittest.TestCase):
    def test_phone_css_and_containers(self):
        app = (ROOT/'app.py').read_text()
        for needle in ('.st-key-mobile_nav', '.st-key-mobile_preview', 'div:has(> .st-key-mobile_preview)',
                       "key='mobile_nav_select'", 'min-height:44px'):
            self.assertIn(needle, app)
        studio = (ROOT/'studio_ui.py').read_text()
        self.assertIn("st.container(key='mobile_preview')", studio)
        self.assertIn("st.container(key='page_head')", studio)
        self.assertIn("with st.expander('✍️ Didascalia per il post", studio)


if __name__ == '__main__':
    unittest.main()
