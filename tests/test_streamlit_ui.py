"""Real Streamlit AppTest integration. Skipped only if Streamlit is unavailable.
Custom JavaScript components require the separate browser smoke tests.
"""
import importlib.util
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from studio_state import empty_library

AVAILABLE=importlib.util.find_spec('streamlit') is not None


@unittest.skipUnless(AVAILABLE,'Streamlit non installato: AppTest non eseguito')
class StreamlitTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60)
        app.session_state['studio_library']=empty_library()
        return app.run()

    def assert_clean(self,app):
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(len(app.error),0,str(app.error))

    def test_all_three_models_render_and_preserve_state(self):
        app=self.app();self.assert_clean(app)
        for template in ('Matchday Screen','Match Result','Starting 7','Match Result'):
            app.radio('studio_template').set_value(template).run()
            self.assert_clean(app)
        app.number_input('mr_0_home_score').set_value(3).run()
        app.radio('studio_template').set_value('Starting 7').run()
        app.radio('studio_template').set_value('Match Result').run()
        self.assertEqual(app.number_input('mr_0_home_score').value,3)
        self.assert_clean(app)

    def test_preset_and_format_keep_score_and_generate_png(self):
        app=self.app()
        app.radio('studio_template').set_value('Match Result').run()
        app.number_input('mr_0_home_score').set_value(4).run()
        app.selectbox('mr_0_preset_choice').set_value('winter').run()
        app.button('mr_0_apply_preset').click().run()
        self.assertEqual(app.session_state['studio_models']['Match Result']['home_score'],4)
        app.selectbox('mr_1_format').set_value('Post 4:5').run()
        self.assertEqual(app.session_state['studio_models']['Match Result']['positions']['score'],[270,354])
        app.button('mr_2_generate_png').click().run()
        from PIL import Image
        import io
        self.assertEqual(Image.open(io.BytesIO(app.session_state['png_Match Result']['data'])).size,(1080,1350))
        self.assert_clean(app)

    def test_matchday_to_result_import(self):
        app=self.app()
        app.radio('studio_template').set_value('Matchday Screen').run()
        app.text_input('md_0_away_name').input('SPORTING TEST').run()
        app.radio('studio_template').set_value('Match Result').run()
        app.number_input('mr_0_home_score').set_value(9).run()
        app.checkbox('mr_0_confirm_import').check().run()
        app.button('mr_0_import_match').click().run()
        c=app.session_state['studio_models']['Match Result']
        self.assertEqual(c['away_name'],'SPORTING TEST')
        self.assertEqual(c['home_score'],0)
        self.assert_clean(app)


if __name__=='__main__':unittest.main()
