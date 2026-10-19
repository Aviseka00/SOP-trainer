import unittest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from sop_studio.avatar import readiness, render_presenter

class PresenterAdapterTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('SOP_TEST_AVATAR') == '1', 'Requires completed real presenter benchmark and model cache')
    def test_real_cached_presenter_composes_with_original_audio(self):
        from sop_studio.composition import ROOT, render
        from sop_studio.schema import file_hash, approve
        from sop_studio.ingestion import storyboard
        import imageio_ffmpeg
        benchmark = json.loads((ROOT/'models/sadtalker/benchmark.json').read_text(encoding='utf-8'))
        audio = next(p for p in (ROOT/'cache/speech').glob('*.wav') if file_hash(p) == benchmark['audio_sha256'])
        portrait = ROOT/'approved_media/presenters/fictional_educator.png'
        row = storyboard(benchmark['test_text'])[0]
        row['layout'] = 'Presenter circular picture-in-picture'
        approve(row, 'Engineering acceptance test')
        temp = ROOT/'.test_tmp'
        temp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            files = render([row], 'Actual AI presenter test', 'Windows offline', '', 155, preexisting_audio=[str(audio)], output_dir=folder,
                avatar={'portrait':str(portrait), 'portrait_sha256':file_hash(portrait), 'device':'cpu', 'expression_scale':1.0, 'pose_style':0})
            manifest = json.loads(files[2].read_text(encoding='utf-8'))
            self.assertEqual('SadTalker audio-driven face', manifest['timeline'][0]['presenter']['type'])
            self.assertEqual(benchmark['output_sha256'], manifest['timeline'][0]['presenter']['generation']['output_sha256'])
            self.assertEqual(manifest['duration_frames'], imageio_ffmpeg.count_frames_and_secs(str(files[0]))[0])

    def test_missing_engine_reports_setup_instead_of_fake_output(self):
        with patch('sop_studio.avatar.readiness', return_value={'files_present':False, 'missing':['checkpoint']}):
            with self.assertRaisesRegex(RuntimeError, 'not installed'):
                render_presenter('missing.png', 'missing.wav')

    def test_invalid_controls_rejected_before_inference(self):
        with self.assertRaisesRegex(ValueError, 'auto GPU/CPU'):
            render_presenter('image.png', 'audio.wav', device='unknown')
        with self.assertRaises(ValueError):
            render_presenter('image.png', 'audio.wav', expression_scale=99)
        with self.assertRaises(ValueError):
            render_presenter('image.png', 'audio.wav', pose_style=99)

if __name__ == '__main__':
    unittest.main()
