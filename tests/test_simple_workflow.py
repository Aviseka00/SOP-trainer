import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from streamlit.testing.v1 import AppTest
from sop_studio.schema import file_hash
from sop_studio.composition import preflight

ROOT = Path(__file__).resolve().parent.parent

class SimpleWorkflowTests(unittest.TestCase):
    def test_five_steps_from_paste_through_approved_render_request(self):
        app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
        self.assertEqual('Create training', app.sidebar.radio[0].value)
        next(t for t in app.text_area if t.label == 'Paste your SOP').set_value('Apply approved soap to both hands.').run()
        next(b for b in app.button if b.label == 'Use pasted SOP →').click().run()
        self.assertEqual(1, app.session_state['simple_step'])
        next(b for b in app.button if b.label == 'Generate training content').click().run()
        self.assertEqual(1, len(app.session_state['project']['scenes']))
        next(b for b in app.button if b.label == 'Continue →').click().run()
        with patch('sop_studio.simple_workflow.installed_voices', return_value=[{'id':'test-voice', 'name':'Test narrator'}]):
            next(b for b in app.button if b.label == 'Find available voices').click().run()
        next(b for b in app.button if b.label == 'Use this voice').click().run()
        self.assertEqual('test-voice', app.session_state['project']['settings']['voice'])
        next(b for b in app.button if b.label == 'Continue →').click().run()
        with tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp') as folder:
            image = Path(folder)/'reviewed.png'
            Image.new('RGB', (320, 180), 'green').save(image)
            project = app.session_state['project']
            row = project['scenes'][0]
            record = {'asset_id':'a'*32, 'path': str(image), 'sha256':file_hash(image), 'sop_id':project['sop_id'],
                      'revision':project['metadata'].get('revision',''), 'status':'approved', 'description':'Test visual', 'reviewer':'Test'}
            project['scene_assets'][row['scene_id']] = record
            app.run()
            next(t for t in app.text_input if t.label == 'Your reviewer name').set_value('Reviewer').run()
            next(t for t in app.text_input if t.label == 'Review notes').set_value('Compared with source.').run()
            next(c for c in app.checkbox if c.label.startswith('I checked this scene')).set_value(True).run()
            with patch('sop_studio.media.MediaLibrary.review', return_value=record):
                next(b for b in app.button if b.label == 'Approve this scene').click().run()
            self.assertTrue(app.session_state['project']['scenes'][0]['approved'])
            self.assertEqual([], list(app.exception))
            next(b for b in app.button if b.label == 'Continue →').click().run()
            next(c for c in app.checkbox if c.label.startswith('Generate this video.')).set_value(True).run()
            self.assertFalse(next(b for b in app.button if b.label == 'Generate final training video').disabled)
            fake_job = ROOT/'jobs'/('f'*32)
            with patch('sop_studio.simple_workflow.jobs.start', return_value=fake_job) as start, patch('sop_studio.simple_workflow.jobs.status', return_value={'state':'cancelled', 'progress':0}):
                next(b for b in app.button if b.label == 'Generate final training video').click().run()
                request = start.call_args.args[0]
                self.assertEqual('test-voice', request['voice'])
                self.assertTrue(request['production']['burn_captions'])
                self.assertEqual(1, len(preflight(request['rows'], {}, None, None, True)))
                self.assertIn('scene_assets', request['metadata'])
            self.assertEqual([], list(app.exception))

    def test_empty_project_blocks_content_and_final_export(self):
        app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=30).run()
        next(b for b in app.sidebar.button if b.label == '2 · Generate content').click().run()
        self.assertTrue(next(b for b in app.button if b.label == 'Generate training content').disabled)
        next(b for b in app.sidebar.button if b.label == '5 · Generate training video').click().run()
        self.assertTrue(next(b for b in app.button if b.label == 'Generate final training video').disabled)
        next(b for b in app.button if b.label == 'Fix').click().run()
        self.assertEqual(0, app.session_state['simple_step'])
        self.assertEqual([], list(app.exception))
