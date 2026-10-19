"""Presenter production preparation and explicit cloud audition."""
from pathlib import Path
import streamlit as st
from . import jobs, credentials
from .presenter_quality import coverage, apply_quality_preset, audition_signature
from .schema import now, file_hash

def preparation(project, save):
    st.subheader('Prepare a complete presenter video')
    st.caption('Apply a consistent export preset, check source coverage, then inspect one actual presenter performance before full production.')
    if st.button('Apply polished training preset'):
        apply_quality_preset(project)
        save('Applied polished training preset and complete-source check')
        st.success('1080p landscape export, high contrast captions, short fades and full source coverage checks enabled. Provider source resolution is unchanged; higher export resolution does not add source detail.')
    report = coverage(project)
    st.metric('Source segments represented in storyboard', f'{report["covered"]} / {report["total"]}')
    st.caption('Coverage compares retained source instructions. It does not certify narration completeness or correctness; compare edited narration with the source.')
    if report['missing']:
        with st.expander('Source segments missing from this video'):
            for row in report['missing']:
                st.write(row['reference'] + ' · ' + row['original_instruction'])
        st.info('Source document → Build traceable storyboard retains all source segments. Summary mode intentionally selects fewer points.')
    config = project.get('avatar', {})
    if config.get('provider') not in ('heygen', 'synthesia') or not project['scenes']:
        st.info('Select a cloud presenter below and create scenes to audition the actual speaking performance.')
        return
    selected = st.selectbox('Presenter audition scene', range(len(project['scenes'])), format_func=lambda i: f'Scene {i+1}: {project["scenes"][i]["narration"][:70]}')
    text = project['scenes'][selected]['narration']
    signature = audition_signature(config, text)
    st.write(text)
    st.caption('This audition submits the entire selected scene. Choose a short scene to limit generation time and provider usage. Completed matching performances are cached and reused during full export.')
    consent = st.checkbox('Generate this cloud audition using provider credits and send this scene narration to the selected provider.')
    active = project.get('cloud_audition', {})
    state = jobs.status(Path(active['job'])) if active.get('job') else None
    busy = bool(state and state['state'] in ('queued', 'running'))
    if st.button('Generate actual cloud presenter audition', disabled=not consent or busy):
        try:
            name = {'heygen': 'HEYGEN_API_KEY', 'synthesia': 'SYNTHESIA_API_KEY'}[config['provider']]
            folder = jobs.start({'task': 'cloud_audition', 'text': text, 'avatar': config}, environment=credentials.environment(st.session_state, (name,)))
            project['cloud_audition'] = {'job': str(folder), 'signature': signature}
            save('Started explicitly requested cloud presenter audition')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    @st.fragment(run_every=2)
    def status():
        active = st.session_state.project.get('cloud_audition', {})
        if not active.get('job'):
            return
        state = jobs.status(Path(active['job']))
        st.caption('Cloud audition: ' + state['state'])
        if state['state'] in ('queued', 'running'):
            if st.button('Cancel cloud audition'):
                jobs.cancel(Path(active['job']))
            st.caption('Cancellation stops local waiting; the provider may continue processing and charge for a submitted job.')
        elif state['state'] == 'complete':
            st.video(state['video'])
            current = active['signature'] == signature
            if not current:
                st.warning('Presenter settings or selected narration differ from this audition.')
            reviewed = st.checkbox('I watched the entire clip and checked pronunciation, lip sync, identity stability, gestures and pacing.', key='audition_review_' + active['signature'])
            if st.button('Record presenter quality review', disabled=not current or not reviewed):
                st.session_state.project['presenter_quality_review'] = {'signature': signature, 'video_sha256': file_hash(state['video']), 'at': now()}
                save('Presenter audition playback reviewed')
                st.success('Playback review recorded for this presenter configuration and narration.')
        else:
            st.error(state.get('error', 'Audition interrupted.'))
    status()
