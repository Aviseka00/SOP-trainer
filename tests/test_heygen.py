import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sop_studio import heygen

CONFIG = {'avatar_id':heygen.DEFAULT_SCIENTIST, 'voice_id':heygen.DEFAULT_VOICE, 'cloud_authorized':True}


class CloudTests(unittest.TestCase):
    def test_cloud_composition_keeps_provider_audio(self):
        import json
        import wave
        from sop_studio.composition import ROOT, render
        from sop_studio.ingestion import storyboard
        from sop_studio.schema import approve, file_hash
        from media_fixture import presenter_clip
        clip = presenter_clip(ROOT)
        self.assertTrue(clip.is_file())
        temp = ROOT/'.test_tmp'
        temp.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp) as folder:
            audio = Path(folder)/'provider.wav'
            with wave.open(str(audio), 'wb') as output:
                output.setparams((1,2,48000,0,'NONE','not compressed'))
                output.writeframes(b'\x00\x00'*48000)
            scene = storyboard('Inspect the equipment before starting work.')[0]
            scene['layout'] = 'Presenter side-by-side'
            approve(scene, 'Engineering test')
            with patch.object(heygen, 'configured', return_value=True), patch.object(heygen, 'render_cloud', return_value=(clip,audio,{'engine':'HeyGen Avatar IV','video_id':'test'})), patch('sop_studio.composition.generate_cached', side_effect=AssertionError('Must not replace provider speech')):
                files = render([scene], 'Cloud composition fixture', 'Windows offline', '', 155, output_dir=folder, avatar={'provider':'heygen', **CONFIG})
            manifest = json.loads(files[2].read_text())
            self.assertEqual(file_hash(audio), manifest['timeline'][0]['audio']['sha256'])
            self.assertEqual('HeyGen cloud performance', manifest['timeline'][0]['presenter']['type'])
            self.assertEqual('HeyGen', manifest['speech']['engine'])

    def test_missing_key_or_authorization_prevents_submission(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(heygen, 'api') as api:
            with self.assertRaises(ValueError):
                heygen.render_cloud('Hello', CONFIG, Path('.'))
            api.assert_not_called()

    def test_media_urls_cannot_read_local_network_or_send_credentials(self):
        for url in ['http://files.heygen.ai/a.mp4', 'https://127.0.0.1/a', 'https://heygen.ai.evil.test/a', 'https://user@heygen.ai/a', 'https://heygen.ai:8080/a']:
            self.assertFalse(heygen.trusted_media(url))
        self.assertTrue(heygen.trusted_media('https://resource2.heygen.ai/video.mp4'))

    def test_unknown_paid_submission_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'HEYGEN_API_KEY':'test-secret'}), patch.object(heygen, 'api', side_effect=RuntimeError('connection interrupted')) as api:
            with self.assertRaises(RuntimeError):
                heygen.render_cloud('Hello', CONFIG, tmp)
            api.assert_called_once()
            self.assertEqual('avatar', api.call_args.args[1]['type'])
            self.assertEqual('Hello', api.call_args.args[1]['script'])
            with self.assertRaisesRegex(RuntimeError, 'unknown outcome'):
                heygen.render_cloud('Hello', CONFIG, tmp)
            api.assert_called_once()
            journal = next(Path(tmp).rglob('submission.json'))
            self.assertNotIn('test-secret', journal.read_text())

    def test_failed_remote_job_is_resumed_without_another_paid_post(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'HEYGEN_API_KEY':'test-secret'}), patch.object(heygen, 'api', side_effect=[{'video_id':'testvideo'}, {'status':'failed'}, {'status':'failed'}]) as api:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'job failed'):
                    heygen.render_cloud('Hello', CONFIG, tmp)
            self.assertEqual(1, sum(len(call.args) > 1 for call in api.call_args_list))
