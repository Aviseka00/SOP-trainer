import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sop_studio import credentials, cloud_io, synthesia, kling
from sop_studio.composition import ROOT
from sop_studio.ingestion import storyboard
from sop_studio.schema import file_hash


class ProviderTests(unittest.TestCase):
    def temporary(self):
        folder = ROOT/'.test_tmp'
        folder.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=folder)

    @unittest.skipUnless(os.name=='nt','Windows current-user encryption')
    def test_windows_encrypted_keys_roundtrip_without_plaintext(self):
        with self.temporary() as root:
            values = {'SYNTHESIA_API_KEY':'dummy-synthesia-secret','KLING_API_KEY':'dummy-kling-secret'}
            credentials.save(root,values)
            data = (Path(root)/'.local/credentials.dpapi').read_bytes()
            self.assertNotIn(b'dummy-synthesia-secret',data)
            self.assertNotIn(b'dummy-kling-secret',data)
            self.assertEqual(values,credentials.load(root))

    def test_credentials_are_filtered_for_selected_worker(self):
        values = {'synthesia_api_key':'test-synth','heygen_api_key':'test-heygen','kling_api_key':'test-kling'}
        self.assertEqual({'SYNTHESIA_API_KEY':'test-synth'},credentials.environment(values,('SYNTHESIA_API_KEY',)))

    def test_worker_receives_only_its_provider_secret_outside_request_json(self):
        from sop_studio import jobs
        from unittest.mock import Mock
        child = Mock(pid=424242)
        with self.temporary() as root, patch.object(jobs,'ROOT',Path(root)), patch.dict(os.environ,{'HEYGEN_API_KEY':'unrelated-heygen','SYNTHESIA_API_KEY':'unrelated-synth','KLING_API_KEY':'env-kling'}), patch.object(jobs.subprocess,'Popen',return_value=child) as launch:
            folder = jobs.start({'task':'generate_visuals','provider':'kling'},environment={'KLING_API_KEY':'session-kling'})
            env = launch.call_args.kwargs['env']
            self.assertEqual('session-kling',env['KLING_API_KEY'])
            self.assertNotIn('HEYGEN_API_KEY',env)
            self.assertNotIn('SYNTHESIA_API_KEY',env)
            self.assertNotIn('session-kling',(folder/'request.json').read_text())
            jobs._workers.pop(folder.name,None)

    def test_missing_credentials_never_submit(self):
        with patch.dict(os.environ,{},clear=True), patch.object(cloud_io,'request') as request:
            with self.assertRaises(ValueError):
                synthesia.render_cloud('Hello',{'avatar_id':'test','cloud_authorized':True},ROOT)
            with self.assertRaises(ValueError):
                kling.generate(storyboard('Inspect equipment before use.')[0],ROOT,{'cloud_authorized':True})
            request.assert_not_called()

    def test_synthesia_keeps_source_script_private_and_decodes_original_speech(self):
        from media_fixture import presenter_clip
        fixture = presenter_clip(ROOT)
        with self.temporary() as root, patch.dict(os.environ,{'SYNTHESIA_API_KEY':'test-secret'}):
            def task(*args):
                payload = args[2]
                self.assertEqual('private',payload['visibility'])
                self.assertEqual('Exact speech, 20 seconds.',payload['input'][0]['scriptText'])
                self.assertTrue(payload['test'])
                folder = Path(root)/'cache/synthesia'/synthesia.digest(payload)
                folder.mkdir(parents=True)
                return fixture,{'task_id':'test-synth'}
            with patch.object(cloud_io,'task',side_effect=task):
                video,audio,record = synthesia.render_cloud('Exact speech, 20 seconds.',{'avatar_id':'authorized_avatar','cloud_authorized':True},root)
            self.assertEqual(fixture,video)
            self.assertTrue(audio.is_file())
            self.assertEqual(file_hash(audio),record['audio_sha256'])
            self.assertNotIn('test-secret',json.dumps(record))

    def test_kling_context_generation_payload_and_provenance(self):
        from media_fixture import presenter_clip
        fixture = presenter_clip(ROOT)
        scene = storyboard('Apply approved soap to both hands.')[0]
        with self.temporary() as root, patch.dict(os.environ,{'KLING_API_KEY':'test-secret'}):
            def task(*args):
                payload = args[2]
                self.assertIn(scene['narration'],payload['prompt'])
                self.assertEqual('off',payload['sound'])
                self.assertEqual('5',payload['duration'])
                folder = Path(root)/'cache/kling'/kling.digest(payload)
                folder.mkdir(parents=True)
                return fixture,{'task_id':'test-kling'}
            with patch.object(cloud_io,'task',side_effect=task):
                record = kling.generate(scene,root,{'cloud_authorized':True})
            self.assertEqual('Kling contextual clip',record['template'])
            self.assertIn('draft',record['review_status'])
            self.assertNotIn('test-secret',json.dumps(record))

    def test_ambiguous_paid_task_is_not_submitted_twice(self):
        with self.temporary() as root:
            from unittest.mock import Mock
            submit = Mock(side_effect=RuntimeError('connection lost'))
            def attempt():
                return cloud_io.task(root,'test',{'prompt':'example'},submit,Mock(),lambda r:r['id'],lambda r:r['status'],('done',),('failed',),lambda r:r['url'],('example.com',))
            with self.assertRaises(RuntimeError):
                attempt()
            with self.assertRaisesRegex(RuntimeError,'unknown outcome'):
                attempt()
            submit.assert_called_once()

    def test_kling_api_uses_official_bearer_endpoint(self):
        with patch.object(cloud_io,'request',return_value={'code':0,'data':{'task_id':'test'}}) as request:
            kling.api('videos/text2video',{'prompt':'example'},key='test-api-key')
        self.assertEqual('https://api-singapore.klingai.com/v1/videos/text2video',request.call_args.args[0])
        self.assertEqual('Bearer test-api-key',request.call_args.args[1])

    def test_media_host_validation(self):
        self.assertTrue(cloud_io.trusted_media('https://cdn.synthesia.io/clip.mp4',('synthesia.io',)))
        self.assertFalse(cloud_io.trusted_media('https://synthesia.io.evil.test/clip.mp4',('synthesia.io',)))
        self.assertFalse(cloud_io.trusted_media('https://127.0.0.1/a',('synthesia.io',)))
