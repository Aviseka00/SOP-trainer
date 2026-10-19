import json
import tempfile
import time
import unittest
import wave
from pathlib import Path
from PIL import ImageChops
from sop_studio.visuals import choose_template, frame, generate, TEMPLATES
from sop_studio.ingestion import storyboard
from sop_studio.media import MediaLibrary, visual_content_hash, scene_asset, asset_current
from sop_studio.schema import approve, file_hash
from sop_studio.composition import render, preflight
from sop_studio.diagnostics import ffmpeg
from sop_studio import jobs

ROOT = Path(__file__).resolve().parent.parent

class VisualTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.test_tmp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'.test_tmp')
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def test_context_selection_distinguishes_actions_and_prohibitions(self):
        examples = [('Apply approved soap to both hands.', 'Soap application'),
                    ('Wet both hands with water.', 'Hand wetting'),
                    ('Rub your palms together.', 'Hand rubbing'), ('Rinse both hands.', 'Hand rinsing'),
                    ('Dry hands using the approved method.', 'Hand drying'),
                    ('Show airflow in the fluid bed dryer.', 'Fluid bed dryer'),
                    ('Do not apply an unapproved soap.', 'Safety warning')]
        for text, template in examples:
            self.assertEqual(template, choose_template(storyboard(text)[0]))

    def test_every_template_renders_real_pixels(self):
        row = storyboard('Apply the approved soap to both hands.')[0]
        fingerprints = []
        for template in TEMPLATES[1:]:
            image = frame(row, template, .25)
            self.assertEqual((960, 540), image.size)
            self.assertGreater(len(image.getcolors(960*540)), 10)
            fingerprints.append(image.tobytes())
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        self.assertIsNotNone(ImageChops.difference(frame(row, 'Hand rinsing', 0), frame(row, 'Hand rinsing', .5)).getbbox())

    def test_illustration_cache_and_text_changes(self):
        row = storyboard('Apply approved soap.')[0]
        first = generate(row, self.root, 'Illustration')
        self.assertTrue(Path(first['path']).is_file())
        self.assertEqual(first['path'], generate(row, self.root, 'Illustration')['path'])
        row['narration'] = 'Rinse both hands.'
        self.assertNotEqual(first['path'], generate(row, self.root, 'Illustration')['path'])
        row['narration'] = 'Never apply unapproved soap.'
        self.assertEqual('Safety warning', generate(row, self.root, 'Illustration', 'Soap application')['template'])

    def test_generated_assets_require_review_and_become_stale(self):
        row = storyboard('Apply approved soap.')[0]
        generated = generate(row, self.root, 'Illustration')
        generated['scene_content_hash'] = visual_content_hash(row)
        library = MediaLibrary(self.root)
        record = library.add(generated['path'], row['visual'], 'test diagram', 'local', 'own', 'SOP1', '1', reviewer='should not auto approve', generation=generated)
        self.assertEqual('draft', record['status'])
        project = {'sop_id':'SOP1', 'metadata':{'revision':'1'}, 'scene_assets':{row['scene_id']:record}}
        self.assertTrue(asset_current(record, row, project))
        self.assertEqual(record, scene_asset(project, row))
        with self.assertRaises(ValueError):
            library.review(record, '', '')
        record = library.review(record, 'Technical reviewer', 'Checked depiction against source; schematic only.')
        self.assertEqual('approved', record['status'])
        row['narration'] = 'Rinse hands.'
        self.assertFalse(asset_current(record, row, project))

    @unittest.skipUnless(ffmpeg(), 'FFmpeg unavailable')
    def test_animated_scene_composes_and_preserves_provenance(self):
        row = storyboard('Rub your palms together.')[0]
        generated = generate(row, self.root, 'Animation')
        import imageio_ffmpeg
        self.assertEqual(36, imageio_ffmpeg.count_frames_and_secs(generated['path'])[0])
        row.update(media=generated['path'], media_sha256=file_hash(generated['path']), generation=generated, asset_review={'status':'draft'})
        approve(row, 'Scene reviewer')
        with self.assertRaisesRegex(ValueError, 'technical approval'):
            preflight([row], {}, None, None, True)
        row['asset_review']['status'] = 'approved'
        approve(row, 'Scene reviewer')
        audio = self.root/'test.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setparams((1, 2, 16000, 0, 'NONE', 'none'))
            stream.writeframes(b'\0\0'*9600)
        files = render([row], 'Generated visual integration', 'Windows offline', '', 155, preexisting_audio=[str(audio)], output_dir=self.root/'export', strict_media=True)
        manifest = json.loads(files[2].read_text(encoding='utf-8'))
        self.assertFalse(manifest['timeline'][0]['demonstration']['placeholder'])
        self.assertEqual('Hand rubbing', manifest['timeline'][0]['demonstration']['generation']['template'])

    @unittest.skipUnless(ffmpeg(), 'FFmpeg unavailable')
    def test_background_visual_generation(self):
        rows = storyboard('Apply approved soap.\nRinse both hands.')
        folder = jobs.start({'task':'generate_visuals', 'scenes':rows, 'mode':'Illustration', 'template':'Automatic', 'sop_id':'ENGINEERING-TEST', 'revision':'0'})
        deadline = time.monotonic()+20
        while time.monotonic() < deadline:
            state = jobs.status(folder)
            if state['state'] not in ('queued', 'running'):
                break
            time.sleep(.1)
        self.assertEqual('complete', state['state'], state)
        self.assertEqual(2, len(state['results']))
        self.assertNotEqual(state['results'][0]['record']['path'], state['results'][1]['record']['path'])
        self.assertTrue(all(item['record']['status'] == 'draft' for item in state['results']))

if __name__ == '__main__':
    unittest.main()
