import json
import tempfile
import time
import unittest
import wave
from pathlib import Path
from sop_studio import jobs
from sop_studio.ingestion import storyboard
from sop_studio.schema import approve
from sop_studio.diagnostics import ffmpeg

@unittest.skipUnless(ffmpeg(), 'FFmpeg is not installed')
class BackgroundJobTests(unittest.TestCase):
    def test_background_export_and_failure(self):
        temp_root = Path(__file__).resolve().parent.parent / '.test_tmp'
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as folder:
            root = Path(folder)
            audio = root/'speech.wav'
            with wave.open(str(audio), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'none'))
                stream.writeframes(b'\0\0'*6400)
            rows = storyboard('Apply approved soap.')
            approve(rows[0], 'Engineering job test')
            request = {'rows':rows, 'title':'Worker test', 'engine':'Windows offline', 'voice':'', 'rate':155,
                       'preexisting_audio':[str(audio)], 'output_dir':str(root/'exports')}
            job = jobs.start(request)
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                state = jobs.status(job)
                if state['state'] not in ('queued', 'running'):
                    break
                time.sleep(.15)
            self.assertEqual('complete', state['state'], state)
            self.assertTrue(Path(state['files'][0]).is_file())
            request['preexisting_audio'] = [str(root/'missing.wav')]
            job = jobs.start(request)
            deadline = time.monotonic()+10
            while time.monotonic() < deadline:
                state = jobs.status(job)
                if state['state'] not in ('queued', 'running'):
                    break
                time.sleep(.15)
            self.assertEqual('failed', state['state'])
            self.assertIn('missing', state['error'])

if __name__ == '__main__':
    unittest.main()
