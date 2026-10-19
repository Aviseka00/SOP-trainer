"""Video/audio voice sample preparation and authorized cloning UI."""
import hashlib
from pathlib import Path
import streamlit as st
from . import voice_clone, heygen
from .schema import digest, invalidate

def controls(project, root, save):
    with st.expander('Clone an authorized voice from video or audio', expanded=True):
        st.caption('Upload MP4, MOV, MKV, WebM, AVI or another supported media file. Extraction runs locally. Creating the clone sends only the extracted audio to HeyGen and requires enabled API access. Use clear speech from one authorized speaker; music and overlapping speakers reduce quality.')
        upload = st.file_uploader('Voice reference video or audio', type=voice_clone.EXTENSIONS, key='voice_reference_upload')
        start = st.number_input('Voice sample start (seconds)', min_value=0.0, value=0.0, step=1.0)
        seconds = st.slider('Voice sample length (seconds)', 5, 180, 60)
        st.caption('A clean 1–3 minute recording is preferable. This selects the requested segment; it does not isolate a speaker from a mixed recording.')
        if st.button('Extract voice sample locally', disabled=upload is None):
            try:
                if upload.size > 500*1024**2:
                    raise ValueError('Upload limit: 500 MB.')
                folder = Path(root)/'.local'/'voice_samples'
                folder.mkdir(parents=True, exist_ok=True)
                checksum = hashlib.sha256(upload.getbuffer()).hexdigest()
                source = folder/(checksum + Path(upload.name).suffix.lower())
                if not source.exists():
                    source.write_bytes(upload.getbuffer())
                target = folder/(digest({'source': checksum, 'start': start, 'seconds': seconds}) + '.wav')
                with st.spinner('Extracting the selected audio segment…'):
                    project['voice_sample'] = {**voice_clone.extract_sample(source, target, start, seconds), 'filename': upload.name}
                save('Extracted local voice sample; no cloud submission')
            except Exception as exc:
                st.error('Could not prepare audio. Check that the file has a decodable audio track. ' + str(exc))
        sample = project.get('voice_sample')
        if sample and Path(sample['path']).is_file():
            st.audio(sample['path'])
            st.caption(f"Extracted {sample['duration']:.1f} seconds · level {sample['rms_dbfs']} dBFS. Listen for noise, music, clipping and other speakers before continuing.")
            st.download_button('Download extracted WAV', Path(sample['path']).read_bytes(), 'voice-reference.wav', 'audio/wav')
        secret = st.text_input('HeyGen API key for voice cloning', value=st.session_state.get('heygen_api_key', ''), type='password', key='clone_api_key_input')
        if secret.strip():
            st.session_state.heygen_api_key = secret.strip()
        ready = bool(secret.strip() or heygen.configured())
        speaker = st.text_input('Speaker name / authorization reference')
        name = st.text_input('Cloned voice name', 'Training narrator', max_chars=64)
        consent = st.checkbox('This is my voice, or I have the speaker’s explicit permission to clone and use their voice for this training.')
        transmit = st.checkbox('Send this extracted sample to HeyGen to create a voice clone. I accept the provider’s applicable usage charges.')
        if st.button('Create authorized voice clone', disabled=not sample or not ready or not speaker.strip() or not consent or not transmit):
            try:
                with st.spinner('Submitting the authorized voice sample…'):
                    project['voice_clone'] = voice_clone.create(sample, name, speaker, consent and transmit, root, key=secret.strip() or None)
                save('Authorized voice clone submitted to HeyGen')
                st.success('Clone submitted. Check provider status below before using it.')
            except Exception as exc:
                st.error(str(exc))
        clone = project.get('voice_clone')
        if not clone:
            return
        st.write('Cloned voice: ' + clone['name'] + ' · ' + clone.get('status', 'PENDING'))
        if st.button('Check cloned voice status', disabled=not ready):
            try:
                result = voice_clone.status(clone['voice_id'], key=secret.strip() or None)
                clone.update(status=result.get('status', 'UNKNOWN'), failure_reason=result.get('failure_reason', ''))
                save('Checked voice clone readiness')
            except Exception as exc:
                st.error(str(exc))
        if clone.get('failure_reason'):
            st.error('Provider could not create this clone: ' + clone['failure_reason'])
        preview = st.text_area('Cloned voice audition text', 'This is a synthetic voice preview for our procedure training.', max_chars=5000)
        if st.button('Generate cloned voice audition', disabled=clone.get('status') != 'ACTIVE' or not ready or not transmit or not preview.strip()):
            try:
                with st.spinner('Generating speech using the cloned voice…'):
                    speech = voice_clone.synthesize(preview, clone['voice_id'], root, key=secret.strip() or None)
                st.session_state.clone_audio_preview = speech['path']
            except Exception as exc:
                st.error(str(exc))
        if st.session_state.get('clone_audio_preview') and Path(st.session_state.clone_audio_preview).is_file():
            st.audio(st.session_state.clone_audio_preview)
        avatar = project.get('avatar', {})
        if avatar.get('provider') != 'heygen':
            st.info('Select your HeyGen presenter in Presenter studio, then return here to apply the cloned voice. This clone is not a Windows or Synthesia voice.')
        if st.button('Use cloned voice for AI presenter', disabled=clone.get('status') != 'ACTIVE' or avatar.get('provider') != 'heygen' or not consent):
            avatar.update(voice_id=clone['voice_id'], native_voice_clone=True,
                          voice_consent={'speaker': clone['speaker'], 'consented_at': clone['consented_at'], 'sample_sha256': clone['sample']})
            project.pop('presenter_quality_review', None)
            for row in project['scenes']:
                invalidate(row)
            save('Applied authorized cloned voice; scene and presenter playback review required')
            st.success('Applied. Presenter auditions and export will synthesize cloned speech and lip-sync the presenter to that audio. Re-review scenes and generate a presenter audition.')
