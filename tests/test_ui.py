"""Streamlit script execution and navigation, without a running web server."""
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from pathlib import Path

class WorkspaceTests(unittest.TestCase):
    def test_synthesia_configuration_and_kling_ui_keep_keys_out_of_project(self):
        import json
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        app.sidebar.radio[0].set_value('AI providers').run()
        next(t for t in app.text_input if t.label == 'Synthesia API key (Legacy v2 scope)').set_value('dummy-private-synth').run()
        next(t for t in app.text_input if t.label == 'Kling developer API key').set_value('dummy-private-kling').run()
        next(t for t in app.text_input if t.label == 'Synthesia avatar ID').set_value('authorized_avatar').run()
        next(c for c in app.checkbox if c.label.startswith('This Synthesia avatar')).set_value(True).run()
        next(b for b in app.button if b.label == 'Use Synthesia for presenter scenes').click().run()
        self.assertEqual([],list(app.exception))
        self.assertEqual('synthesia',app.session_state['project']['avatar']['provider'])
        self.assertNotIn('dummy-private',json.dumps(app.session_state['project']))
        app.sidebar.radio[0].set_value('Visual generation').run()
        next(s for s in app.selectbox if s.label=='Visual provider').set_value('Kling AI').run()
        self.assertEqual([],list(app.exception))
        self.assertTrue(next(b for b in app.button if b.label=='Generate for this scene').disabled)
        next(c for c in app.checkbox if c.label.startswith('Send selected scene contexts')).set_value(True).run()
        self.assertFalse(next(b for b in app.button if b.label=='Generate for this scene').disabled)
        self.assertEqual('dummy-private-synth',app.session_state['synthesia_api_key'])
        self.assertEqual('dummy-private-kling',app.session_state['kling_api_key'])

    def test_cloud_configuration_does_not_save_session_key(self):
        import json
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        app.sidebar.radio[0].set_value('Presenter studio').run()
        next(t for t in app.text_input if t.label == 'HeyGen API key (this session only)').set_value('test-memory-only-key').run()
        next(c for c in app.checkbox if c.label.startswith('Send scene narration')).set_value(True).run()
        next(b for b in app.button if b.label == 'Use HeyGen scientist for this project').click().run()
        self.assertEqual([], list(app.exception))
        project = app.session_state['project']
        self.assertEqual('heygen', project['avatar']['provider'])
        self.assertNotIn('test-memory-only-key', json.dumps(project))
        self.assertTrue(all(s['layout'] == 'Presenter side-by-side' and not s['approved'] for s in project['scenes']))
        app.sidebar.radio[0].set_value('Export center').run()
        self.assertEqual('test-memory-only-key', app.session_state['heygen_api_key'])
        self.assertEqual([], list(app.exception))

    def test_summary_to_animation_storyboard_and_source_invalidation(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        app.sidebar.radio[0].set_value('Summary & key points').run()
        next(b for b in app.button if b.label == 'Generate summary & speech draft').click().run()
        self.assertEqual([], list(app.exception))
        brief = app.session_state['project']['training_brief']
        self.assertTrue(brief['points'])
        next(c for c in app.checkbox if c.label.startswith('I compared the summary')).set_value(True).run()
        next(b for b in app.button if b.label == 'Build scenes & contextual animations →').click().run()
        self.assertEqual([], list(app.exception))
        project = app.session_state['project']
        self.assertEqual(len(brief['points']), len(project['scenes']))
        self.assertTrue(project['active_visual_job'])
        self.assertTrue(all(s.get('summary_point_id') for s in project['scenes']))
        from sop_studio import jobs
        jobs.cancel(Path(project['active_visual_job']))
        app.session_state['project']['source_text'] += '\nChanged source.'
        app.run()
        self.assertFalse(any(b.label == 'Build scenes & contextual animations →' for b in app.button))

    @patch('sop_studio.avatar.readiness', return_value={'files_present': True, 'missing': [], 'verification': None})
    def test_fictional_laboratory_presenter_presets(self, _readiness):
        from sop_studio.media import file_hash
        root = Path(__file__).resolve().parent.parent
        app = AppTest.from_file(str(root/'app.py'), default_timeout=30).run()
        app.sidebar.radio[0].set_value('Presenter studio').run()
        for label, filename in [('Lab scientist', 'fictional_lab_scientist.png'),
                                ('Lab technician', 'fictional_lab_technician.png')]:
            next(s for s in app.selectbox if s.label == 'Fictional character').set_value(label).run()
            next(c for c in app.checkbox if c.label.startswith('This is fictional')).set_value(True).run()
            next(b for b in app.button if b.label == 'Use AI presenter for this project').click().run()
            self.assertEqual([], list(app.exception))
            avatar = app.session_state['project']['avatar']
            self.assertEqual(filename, Path(avatar['portrait']).name)
            self.assertEqual(file_hash(root/'approved_media'/'presenters'/filename), avatar['portrait_sha256'])

    def test_storyboard_automatically_starts_animation_generation(self):
        import time
        from sop_studio import jobs
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        app.sidebar.radio[0].set_value('Source document').run()
        next(t for t in app.text_area if t.label == 'Source text').set_value('Apply approved soap to both hands.')
        next(b for b in app.button if b.label == 'Save source information').click().run()
        next(b for b in app.button if b.label.startswith('Build traceable storyboard')).click().run()
        folder = Path(app.session_state['project']['active_visual_job'])
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and jobs.status(folder)['state'] in ('queued', 'running'):
            time.sleep(.1)
        app.sidebar.radio[0].set_value('Visual generation').run()
        self.assertEqual([], list(app.exception))
        record = next(iter(app.session_state['project']['scene_assets'].values()))
        self.assertEqual('Animation', record['generation']['mode'])
        self.assertEqual('Soap application', record['generation']['template'])

    def test_all_pages_and_reruns(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30)
        app.run()
        self.assertEqual([], list(app.exception))
        for page in ['Source document', 'Storyboard & script', 'Presenter & media', 'Visual generation', 'Presenter studio', 'Voice studio', 'Timeline', 'QA review', 'Export center', 'Models & diagnostics', 'Dashboard']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertEqual([], list(app.exception), page)
            self.assertTrue(len(app.title) > 0, page)

    def test_example_edit_invalidates_approval(self):
        from sop_studio.schema import approve
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        self.assertTrue(len(app.session_state['project']['scenes']) > 0)
        row = app.session_state['project']['scenes'][0]
        approve(row, 'Test reviewer')
        app.sidebar.radio[0].set_value('Storyboard & script').run()
        app.text_area[0].set_value('Revised narration')
        next(b for b in app.button if b.label == 'Save scene changes').click().run()
        self.assertEqual([], list(app.exception))
        self.assertFalse(app.session_state['project']['scenes'][0]['approved'])
        app.sidebar.radio[0].set_value('Timeline').run()
        self.assertEqual([], list(app.exception))

    def test_generated_visual_attaches_and_can_be_reviewed(self):
        import time
        from sop_studio import jobs
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        app.sidebar.radio[0].set_value('Visual generation').run()
        next(r for r in app.radio if r.label == 'Output type').set_value('Illustration').run()
        next(b for b in app.button if b.label == 'Generate for this scene').click().run()
        folder = Path(app.session_state['project']['active_visual_job'])
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and jobs.status(folder)['state'] in ('queued', 'running'):
            time.sleep(.1)
        app.run()
        self.assertEqual([], list(app.exception))
        project = app.session_state['project']
        self.assertEqual(1, len(project['scene_assets']))
        next(t for t in app.text_input if t.label == 'Technical reviewer').set_value('Engineering reviewer')
        next(t for t in app.text_area if t.label == 'Technical review notes').set_value('Illustration inspected; test source only.')
        next(c for c in app.checkbox if c.label.startswith('I verified this schematic')).set_value(True)
        next(b for b in app.button if b.label == 'Approve generated visual').click().run()
        self.assertEqual([], list(app.exception))
        self.assertEqual('approved', next(iter(app.session_state['project']['scene_assets'].values()))['status'])
        self.assertFalse(app.session_state['project']['scenes'][0]['approved'])
        app.sidebar.radio[0].set_value('Timeline').run()
        self.assertEqual([], list(app.exception))

if __name__ == '__main__':
    unittest.main()
