import json
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image
from sop_studio.editing import validate_cues, content_digest
from sop_studio.storage import ProjectStore
from sop_studio.schema import validate_project, approve, file_hash
from sop_studio.ingestion import storyboard
from sop_studio.composition import render
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run

class EditingTests(unittest.TestCase):
    def test_guided_navigation_autosave_and_readiness_fix(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        next(b for b in app.button if b.label == 'Explore the hand-hygiene example').click().run()
        app.sidebar.radio[0].set_value('Source document').run()
        next(b for b in app.button if b.label == 'Next →').click().run()
        self.assertEqual('Summary & key points', app.sidebar.radio[0].value)
        app.sidebar.radio[0].set_value('Storyboard & script').run()
        next(t for t in app.text_area if t.label == 'Spoken narration').set_value('Autosaved revised narration.').run()
        self.assertEqual([], list(app.exception))
        project = app.session_state['project']
        saved = json.loads((Path(__file__).resolve().parent.parent/'projects'/project['project_id']/'project.json').read_text())
        self.assertEqual('Autosaved revised narration.', saved['scenes'][0]['narration'])
        app.sidebar.radio[0].set_value('Export center').run()
        next(b for b in app.button if b.label == 'Fix →').click().run()
        self.assertEqual('Voice studio', app.sidebar.radio[0].value)
        self.assertEqual([], list(app.exception))

    def test_restore_keeps_current_version_and_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            store = ProjectStore(Path(folder))
            project = store.save(validate_project({'scenes': [], 'title': 'Before'}))
            original = content_digest(project)
            project['title'] = 'After'
            project = store.save(project)
            restored = store.restore(project['project_id'], store.versions(project['project_id'])[0]['version'])
            self.assertEqual('Before', restored['title'])
            self.assertEqual(original, content_digest(restored))
            self.assertEqual(2, len(store.versions(project['project_id'])))
            with self.assertRaises(ValueError):
                store.restore(project['project_id'], '../project')

    def test_cue_validation(self):
        for cues in [[{'start': 0, 'end': float('nan'), 'text': 'a'}],
                     [{'start': 0, 'end': 2, 'text': 'a'}, {'start': 1, 'end': 3, 'text': 'b'}],
                     [{'start': 0, 'end': 4, 'text': 'a'}]]:
            with self.assertRaises(ValueError):
                validate_cues(cues, 3)

    @unittest.skipUnless(ffmpeg(), 'FFmpeg required')
    def test_timed_visual_frames_and_caption_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base, phrase = root/'base.png', root/'phrase.png'
            Image.new('RGB', (1280, 720), 'red').save(base)
            Image.new('RGB', (1280, 720), 'blue').save(phrase)
            audio = root/'audio.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b'\0\0'*32000)
            row = storyboard('Wash hands with approved soap.')[0]
            row['media'] = str(base)
            row['phrase_cues'] = [{'start': .5, 'end': 1, 'text': 'Approved soap',
                                  'asset': {'path': str(phrase), 'sha256': file_hash(phrase), 'status': 'approved'}}]
            approve(row, 'Test reviewer')
            files = render([row], 'Draft test', 'Windows offline', '', 155, output_dir=root/'out',
                           job_dir=root/'job', preexisting_audio=[audio],
                           production={'burn_captions': True, 'brand': 'Training', 'accent': '#228844',
                                       'caption_style': 'High contrast', 'transition': 'Fade'})
            self.assertIn('00:00:00,500 --> 00:00:01,000', files[1].read_text())
            for time, expected in [(.3, 0), (.7, 2), (1.3, 0)]:
                frame = root/f'{time}.png'
                run([ffmpeg(), '-y', '-loglevel', 'error', '-ss', str(time), '-i', files[0], '-frames:v', '1', frame])
                rgb = Image.open(frame).getpixel((640, 200))
                self.assertEqual(expected, max(range(3), key=lambda i: rgb[i]), rgb)
            self.assertEqual(60, json.loads(files[2].read_text())['duration_frames'])

