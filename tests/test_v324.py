"""3.24: faster on the phone (lighter pages, only what is shown is built)."""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Light(unittest.TestCase):
    def test_finished_png_shown_as_light_jpeg(self):
        from PIL import Image
        import numpy as np
        import app_shell
        noise = (np.random.default_rng(1).random((1920, 1080, 4))*255).astype('uint8')
        out = io.BytesIO()
        Image.fromarray(noise, 'RGBA').save(out, 'PNG')
        png = out.getvalue()
        small = app_shell.preview(png)
        self.assertTrue(small.startswith(b'\xff\xd8'))                       # a JPEG
        self.assertLess(len(small), len(png)/5)
        self.assertEqual(Image.open(io.BytesIO(small)).size, (720, 1280))
        self.assertIs(app_shell.preview(png), small)                         # made once
        self.assertEqual(app_shell.preview(b'not an image'), b'not an image')

    def test_timings_off_by_default(self):
        import perf
        if perf.ON:
            self.skipTest('FLAMINGOS_PERF set in this environment')
        perf.start(); perf.mark('x'); perf.stop('pagina')                     # nothing happens, nothing breaks


class Built(unittest.TestCase):
    def test_only_the_chosen_editor_section(self):
        studio = (ROOT/'studio_ui.py').read_text()
        self.assertNotIn("st.tabs(['✏️ Contenuti', '🎨 Stile', '📤 Esporta'])", studio)
        self.assertIn("part = st.segmented_control('Sezione'", studio)
        self.assertEqual(studio.count("if part == 'export':"), 2)
        self.assertIn('if phone:', studio)                                   # no drag editor on a phone
        self.assertIn('scale = 1 if phone else 2', studio)

    def test_csi_after_the_page_and_week_in_parts(self):
        app = (ROOT/'app.py').read_text()
        self.assertGreater(app.index('auto_update()\n'), app.index('shared_ui.autosave(library)'))
        week = (ROOT/'week_ui.py').read_text()
        self.assertIn('def _phone_week(root, library):', week)

    def test_share_only_on_request(self):
        share = (ROOT/'share.py').read_text()
        self.assertLess(share.index("if st.session_state.get(flag) != mark:"), share.index('components.html(html'))

    def test_archive_confirms_without_the_whole_library(self):
        page = (ROOT/'library_frontend'/'index.html').read_text()
        self.assertIn('function ack(commandId', page)
        lib = (ROOT/'library.py').read_text()
        self.assertIn("result.get('ack')", lib)
        self.assertIn("== 'on':\n        return True", lib)


if __name__ == '__main__':
    unittest.main()
