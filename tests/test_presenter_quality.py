import unittest
from unittest.mock import patch
from sop_studio.ingestion import storyboard
from sop_studio.schema import validate_project
from sop_studio.presenter_quality import coverage, apply_quality_preset, audition_signature
from sop_studio.editing import readiness

class QualityTests(unittest.TestCase):
    def test_cloud_audition_worker_success_failure_and_cancellation(self):
        import json
        import tempfile
        from pathlib import Path
        from sop_studio import jobs
        from sop_studio.process import RenderCancelled
        from sop_studio.storage import atomic_json
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = {'provider': 'heygen', 'cloud_authorized': True}
            atomic_json(root/'request.json', {'task': 'cloud_audition', 'avatar': config, 'text': 'Wash hands.'})
            for outcome, expected in [((root/'video.mp4', root/'audio.wav', {'engine': 'test fixture'}), 'complete'),
                                      (RuntimeError('Provider test failure'), 'failed'),
                                      (RenderCancelled('Cancelled fixture'), 'cancelled')]:
                with patch('sop_studio.heygen.render_cloud') as cloud:
                    if isinstance(outcome, Exception):
                        cloud.side_effect = outcome
                    else:
                        cloud.return_value = outcome
                    jobs.worker(root)
                    cloud.assert_called_once_with('Wash hands.', config, jobs.ROOT, root/'cancel')
                state = json.loads((root/'status.json').read_text())
                self.assertEqual(expected, state['state'])
                if expected == 'complete':
                    self.assertEqual(str(root/'video.mp4'), state['video'])
                elif expected == 'failed':
                    self.assertIn('Provider test failure', state['error'])

    def test_full_source_coverage_and_missing_segments(self):
        text = 'Wash hands with approved soap.\nRecord the activity in the logbook.'
        project = validate_project({'source_text': text, 'scenes': storyboard(text)})
        self.assertEqual([], coverage(project)['missing'])
        project['scenes'].pop()
        self.assertEqual(1, len(coverage(project)['missing']))
        apply_quality_preset(project)
        self.assertTrue(any('absent' in message for _, _, message in readiness(project, lambda r: True, False)))
        self.assertTrue(project['settings']['production']['burn_captions'])
        self.assertEqual('1080p landscape', project['settings']['preset'])

    def test_audition_review_changes_with_voice_or_script(self):
        config = {'provider': 'heygen', 'voice_id': 'voice_a'}
        signature = audition_signature(config, 'Wash hands.')
        self.assertNotEqual(signature, audition_signature(config, 'Rinse hands.'))
        self.assertNotEqual(signature, audition_signature({**config, 'voice_id': 'voice_b'}, 'Wash hands.'))
        project = validate_project({'source_text': 'Wash hands.', 'scenes': storyboard('Wash hands.'), 'avatar': config})
        apply_quality_preset(project)
        self.assertTrue(any('audition' in message for _, _, message in readiness(project, lambda r: True, False)))
        project['presenter_quality_review'] = {'signature': audition_signature(config, project['scenes'][0]['narration'])}
        self.assertFalse(any('audition' in message for _, _, message in readiness(project, lambda r: True, False)))

    def test_preparation_ui_renders_without_cloud_submission(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        with patch('sop_studio.heygen.api') as api:
            app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
            app.sidebar.radio[0].set_value('Presenter studio').run()
            next(b for b in app.button if b.label == 'Apply polished training preset').click().run()
            self.assertEqual([], list(app.exception))
            self.assertTrue(app.session_state['project']['settings']['require_complete_source'])
            api.assert_not_called()
