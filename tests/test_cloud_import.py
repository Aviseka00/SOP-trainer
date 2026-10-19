import tempfile,unittest,ssl
from pathlib import Path
from sop_studio import cloud_import,cloud_io
from sop_studio.schema import digest,file_hash
from sop_studio.composition import ROOT
from sop_studio.diagnostics import ffmpeg
from sop_studio.process import run


class ImportedCloudTests(unittest.TestCase):
    @unittest.skipUnless(ffmpeg(), 'FFmpeg is required')
    def test_exact_narration_and_file_integrity_binding(self):
        temporary=ROOT/'.test_tmp'
        temporary.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary) as folder:
            root=Path(folder)
            media=root/'approved_media'
            media.mkdir()
            video=media/'presenter.mp4'
            run([ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10',
                 '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000', '-t', '1',
                 '-c:v', 'libx264', '-c:a', 'aac', video])
            clip={'path':str(video),'sha256':file_hash(video),'provider':'HeyGen','video_id':'fixture'}
            config={'provider':'imported-cloud','cloud_authorized':True,'clips':{digest('Exact script'):clip}}
            path,audio,record=cloud_import.render_cloud('Exact script',config,root)
            self.assertEqual(video,path)
            self.assertTrue(audio.is_file())
            self.assertEqual(file_hash(audio),record['audio_sha256'])
            with self.assertRaisesRegex(ValueError,'exact narration'):
                cloud_import.render_cloud('Edited script',config,root)
            video.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                cloud_import.render_cloud('Exact script',config,root)

    def test_native_tls_retains_certificate_and_hostname_checks(self):
        context=cloud_io.https_handler()._context
        self.assertEqual(ssl.CERT_REQUIRED,context.verify_mode)
        self.assertTrue(context.check_hostname)
