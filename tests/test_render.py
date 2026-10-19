"""Real FFmpeg rendering; no network or model downloads. Speech test is opt-in."""
import json
import math
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from PIL import Image
from sop_studio.composition import render, ROOT
from sop_studio.diagnostics import ffmpeg
from sop_studio.ingestion import storyboard
from sop_studio.schema import approve, file_hash, LAYOUTS
from sop_studio.process import run

TEST_TEMP = Path(__file__).resolve().parent.parent / '.test_tmp'
TEST_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TEMP)

@unittest.skipUnless(ffmpeg(), 'FFmpeg not installed')
class RenderTests(unittest.TestCase):
    def test_all_layouts_and_artifacts(self):
        with tempfile.TemporaryDirectory(prefix='sop_render_') as folder:
            root = Path(folder)
            image = root / 'asset.png'
            Image.new('RGB', (640, 480), '#3b7863').save(image)
            audio = root / 'tone.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                stream.writeframes(b''.join(struct.pack('<h', int(4000*math.sin(2*math.pi*440*i/16000))) for i in range(6400)))
            presenter = root / 'presenter.mp4'
            run([ffmpeg(), '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=320x480:r=30', '-t', '0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', presenter])
            rows = storyboard('\n'.join(f'{i+1}. Wash hands with approved soap.' for i in range(4)))
            for row, layout in zip(rows, LAYOUTS):
                row.update(layout=layout, media=str(image), media_sha256=file_hash(image))
                approve(row, 'Integration test')
            files = render(rows, 'Render test', 'Windows offline', '', 155, str(presenter), output_dir=root/'exports', preexisting_audio=[str(audio)]*4, strict_media=True)
            manifest = json.loads(files[2].read_text(encoding='utf-8'))
            self.assertEqual(4, len(manifest['timeline']))
            self.assertEqual([1280, 720], manifest['resolution'])
            self.assertEqual(30, manifest['fps'])
            self.assertEqual(48, manifest['duration_frames'])
            self.assertEqual(5, len(manifest['artifacts']))
            for artifact in manifest['artifacts'].values():
                self.assertEqual(artifact['sha256'], file_hash(artifact['path']))
            self.assertTrue(files[0].stat().st_size > 1000)
            import imageio_ffmpeg
            actual_frames, actual_duration = imageio_ffmpeg.count_frames_and_secs(str(files[0]))
            self.assertEqual(48, actual_frames)
            self.assertAlmostEqual(1.6, actual_duration, places=1)
            run([ffmpeg(), '-v', 'error', '-i', files[0], '-f', 'null', '-'])
            # Test portrait and full-screen presenter branch independently.
            render([rows[-1]], 'Portrait', 'Windows offline', '', 155, str(presenter), output_dir=root/'portrait', preexisting_audio=[str(audio)], preset='1080p portrait')
            render([rows[-1]], 'Landscape HD', 'Windows offline', '', 155, str(presenter), output_dir=root/'landscape', preexisting_audio=[str(audio)], preset='1080p landscape')
            rows[-1]['layout'] = 'Presenter circular picture-in-picture'
            approve(rows[-1], 'Integration test')
            render([rows[-1]], 'Circular PiP', 'Windows offline', '', 155, str(presenter), output_dir=root/'circle', preexisting_audio=[str(audio)])

    @unittest.skipUnless(os.environ.get('SOP_TEST_SPEECH') == '1', 'Set SOP_TEST_SPEECH=1 to test installed Windows voices')
    def test_actual_spoken_sop_to_video(self):
        from sop_studio.speech import installed_voices
        voices = installed_voices()
        self.assertTrue(voices)
        from sop_studio.ingestion import extract, source_record
        sample = ROOT / 'examples' / 'hand_hygiene.txt'
        content = sample.read_bytes()
        text = extract(sample.name, content)
        rows = [r for r in storyboard(text) if r['source_section'] in ('3.2', '3.3', '3.4')]
        self.assertEqual(3, len(rows))
        for row in rows:
            approve(row, 'Engineering smoke test — demonstration placeholders')
        files = render(rows, 'Hand hygiene — engineering test only', 'Windows offline', voices[0]['id'], 155,
                       output_dir=ROOT/'outputs'/'acceptance', metadata={'sample': 'fictional demo', 'not_for_training': True, 'source':source_record(sample.name, content, text)})
        manifest = json.loads(files[2].read_text(encoding='utf-8'))
        self.assertEqual(3, len(manifest['timeline']))
        self.assertTrue(all(r['demonstration']['placeholder'] for r in manifest['timeline']))
        self.assertTrue(all(r['audio']['duration'] > 1 for r in manifest['timeline']))
        (ROOT/'outputs'/'acceptance'/'latest.json').write_text(json.dumps([str(p) for p in files]), encoding='utf-8')

if __name__ == '__main__':
    unittest.main()
