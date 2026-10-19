import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sop_studio import voice_clone, heygen
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run
from sop_studio.schema import file_hash

class VoiceCloneTests(unittest.TestCase):
    def test_voice_studio_ui_requires_consent_and_applies_clone(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parent.parent/'app.py'), default_timeout=30).run()
        app.sidebar.radio[0].set_value('Voice studio').run()
        self.assertEqual([], list(app.exception))
        self.assertTrue(next(b for b in app.button if b.label == 'Create authorized voice clone').disabled)
        project = app.session_state['project']
        project['avatar'] = {'provider': 'heygen', 'avatar_id': 'avatar_123', 'voice_id': 'voice_123', 'cloud_authorized': True}
        project['voice_clone'] = {'name': 'Narrator', 'speaker': 'Authorized test speaker', 'voice_id': 'clone_123',
                                  'consented_at': 'test time', 'sample': 'sample hash', 'status': 'ACTIVE'}
        app.run()
        self.assertTrue(next(b for b in app.button if b.label == 'Use cloned voice for AI presenter').disabled)
        next(c for c in app.checkbox if c.label.startswith('This is my voice')).set_value(True).run()
        with patch('sop_studio.heygen.api') as api:
            next(b for b in app.button if b.label == 'Use cloned voice for AI presenter').click().run()
            api.assert_not_called()
        self.assertEqual([], list(app.exception))
        self.assertTrue(app.session_state['project']['avatar']['native_voice_clone'])
        self.assertEqual('clone_123', app.session_state['project']['avatar']['voice_id'])

    @unittest.skipUnless(ffmpeg(), 'FFmpeg required')
    def test_extract_mp4_audio_and_reject_silent_and_missing_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            media = root/'sample.mp4'
            run([ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '6', '-c:v', 'libx264', '-c:a', 'aac', media])
            sample = voice_clone.extract_sample(media, root/'sample.wav', 0, 5)
            self.assertGreaterEqual(sample['duration'], 5)
            self.assertEqual(file_hash(root/'sample.wav'), sample['sha256'])
            with self.assertRaises(ValueError):
                voice_clone.extract_sample(media, root/'bad.wav', -1, 5)
            silent = root/'silent.wav'
            import wave
            with wave.open(str(silent), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'none'))
                stream.writeframes(b'\0\0'*96000)
            with self.assertRaises(ValueError):
                voice_clone.extract_sample(silent, root/'bad.wav', 0, 5)
            video = root/'no_audio.mp4'
            run([ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10', '-t', '6', '-c:v', 'libx264', video])
            with self.assertRaises(Exception):
                voice_clone.extract_sample(video, root/'bad.wav', 0, 5)

    def test_consent_deduplication_and_uncertain_clone(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'sample.wav'
            source.write_bytes(b'audio fixture')
            sample = {'path': str(source), 'sha256': file_hash(source)}
            with patch('sop_studio.heygen.api', return_value={'voice_id': 'clone_123'}) as api:
                with self.assertRaises(ValueError):
                    voice_clone.create(sample, 'Narrator', 'Speaker', False, root)
                api.assert_not_called()
                first = voice_clone.create(sample, 'Narrator', 'Speaker', True, root, key='private-test-key')
                second = voice_clone.create(sample, 'Narrator', 'Speaker', True, root)
                self.assertEqual(first['voice_id'], second['voice_id'])
                api.assert_called_once()
                self.assertEqual('base64', api.call_args.args[1]['audio'][0]['type'])
                self.assertNotIn('private-test-key', json.dumps(first))
            with patch('sop_studio.heygen.api', side_effect=RuntimeError('timeout')) as api:
                with self.assertRaises(RuntimeError):
                    voice_clone.create(sample, 'Another clone', 'Speaker', True, root)
                with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                    voice_clone.create(sample, 'Another clone', 'Speaker', True, root)
                api.assert_called_once()

    def test_speech_cache_and_no_unsupported_instant_voice_fields(self):
        import wave
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def download(url, output, cancel):
                with wave.open(str(output), 'wb') as stream:
                    stream.setparams((1, 2, 16000, 0, 'NONE', 'none'))
                    stream.writeframes(b'\1\0'*16000)
            with patch('sop_studio.heygen.api', return_value={'audio_url': 'https://files.heygen.ai/sample.wav'}) as api, patch('sop_studio.heygen.download', side_effect=download):
                a = voice_clone.synthesize('Test narration.', 'clone_123', root)
                b = voice_clone.synthesize('Test narration.', 'clone_123', root)
                api.assert_called_once()
                self.assertEqual(a, b)
                self.assertNotIn('speed', api.call_args.args[1])
                self.assertNotIn('pitch', api.call_args.args[1])
            with self.assertRaises(ValueError):
                voice_clone.synthesize('a'*5001, 'clone_123', root)

    def test_clone_presenter_submits_generated_audio_instead_of_script(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            seen = []
            def api(route, payload=None):
                if route == 'videos':
                    seen.append(payload)
                    return {'video_id': 'video_test'}
                return {'status': 'failed'}
            config = {'avatar_id': 'avatar_test', 'voice_id': 'clone_123', 'cloud_authorized': True,
                      'native_voice_clone': True, 'voice_consent': {'speaker': 'Test'}}
            with patch('sop_studio.heygen.configured', return_value=True), patch('sop_studio.heygen.api', side_effect=api), patch('sop_studio.voice_clone.synthesize', return_value={'audio_url': 'https://files.heygen.ai/speech.wav'}):
                with self.assertRaises(RuntimeError):
                    heygen.render_cloud('Test speech.', config, root)
                self.assertEqual('https://files.heygen.ai/speech.wav', seen[0]['audio_url'])
                self.assertNotIn('script', seen[0])
                self.assertNotIn('voice_id', seen[0])
                with self.assertRaises(RuntimeError):
                    heygen.render_cloud('Test speech.', config, root)
                self.assertEqual(1, len(seen))
