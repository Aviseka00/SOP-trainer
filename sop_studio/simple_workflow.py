"""Five-step production interface backed by the existing reviewed render pipeline."""
import copy
import hashlib
import json
from pathlib import Path
import streamlit as st
from . import jobs, credentials, heygen
from .ingestion import extract, source_record, storyboard, metadata
from .summary import build_brief, brief_scenes
from .schema import digest, invalidate, approve, file_hash, LAYOUTS
from .media import scene_asset, asset_current, visual_content_hash
from .speech import installed_voices, generate_cached
from .editing import readiness
from .composition import PRESETS

STEPS = ['Upload SOP', 'Generate content', 'Add voice', 'Design video', 'Generate training video']

def go(step):
    st.session_state.simple_step = step
    st.session_state._next_page = 'Create training'

def clear_reviews(project):
    for row in project['scenes']:
        invalidate(row)
    project.pop('presenter_quality_review', None)

def render(project, root, store, library, save, load_project, new_project, is_approved, navigate):
    step = min(4, max(0, st.session_state.get('simple_step', 0)))
    settings = project['settings']
    rows = project['scenes']
    st.progress((step+1)/5, text=f'Step {step+1} of 5 · {STEPS[step]}')
    st.header(STEPS[step])

    if step == 0:
        st.write('Upload your procedure to start a training video.')
        upload = st.file_uploader('SOP document', type=['pdf', 'docx', 'txt'], help='PDF, Word or text · maximum 25 MB', key='simple_sop')
        if st.button('Use this SOP →', type='primary', disabled=upload is None):
            try:
                text = extract(upload.name, upload.getvalue())
                record = source_record(upload.name, upload.getvalue(), text)
                path = store.folder(project['project_id'])/'sources'/(record['sha256']+Path(upload.name).suffix.lower())
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(upload.getvalue())
                project.update(source_text=text, title=record['title'] or Path(upload.name).stem, sop_id=record['sop_number'] or '')
                project['metadata'].update(record, source_path=str(path))
                clear_reviews(project)
                save('SOP uploaded in guided workflow')
                go(1)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        with st.expander('Or paste SOP text'):
            text = st.text_area('Paste your SOP', project['source_text'], height=220)
            if st.button('Use pasted SOP →', disabled=not text.strip()):
                project['source_text'] = text
                project['metadata'] = metadata(text)
                clear_reviews(project)
                save('Pasted SOP source retained')
                go(1)
                st.rerun()
        if project['source_text']:
            st.success('SOP ready · ' + project['title'])
        with st.expander('Try an example or resume a project'):
            if st.button('Explore the hand-hygiene example'):
                example = new_project()
                example['source_text'] = (root/'examples'/'hand_hygiene.txt').read_text(encoding='utf-8')
                example['title'] = 'Hand hygiene training example'
                example['scenes'] = storyboard(example['source_text'])
                load_project(example)
                save('Example project created')
                st.rerun()
            recent = store.list()
            if recent and st.button('Resume latest project'):
                load_project(store.load(recent[0]['project_id']))
                st.rerun()

    elif step == 1:
        st.write('Create the script, then read and adjust what the presenter will say.')
        mode = st.radio('Content length', ['Complete SOP', 'Short overview'], horizontal=True)
        if mode == 'Short overview':
            st.caption('An overview selects key points and can omit source instructions.')
        if rows:
            st.caption('Generating again replaces the current scenes. Previous saves remain in version history.')
        if st.button('Generate training content', type='primary', disabled=not project['source_text'].strip()):
            try:
                project['scenes'] = storyboard(project['source_text']) if mode == 'Complete SOP' else brief_scenes(build_brief(project['source_text']), project['source_text'])
                if project.get('avatar'):
                    for row in project['scenes']:
                        row['layout'] = 'Presenter side-by-side'
                project['metadata']['storyboard_source_hash'] = hashlib.sha256(project['source_text'].encode()).hexdigest()
                settings['require_complete_source'] = mode == 'Complete SOP'
                project['scene_assets'] = {}
                project.pop('active_visual_job', None)
                project.pop('presenter_quality_review', None)
                st.session_state.generation += 1
                save('Training content generated: ' + mode)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if rows:
            st.caption(f'{len(rows)} scenes · approximately {sum(len(r["narration"].split()) for r in rows)/155:.1f} minutes')
            selected = st.selectbox('Edit scene', range(len(rows)), format_func=lambda i:f'{i+1}. {rows[i]["narration"][:65]}')
            row = rows[selected]
            with st.form('simple_script_' + row['scene_id']):
                narration = st.text_area('What the presenter will say', row['narration'], height=170)
                with st.expander('Compare original SOP instruction'):
                    st.write(row['original_instruction'])
                    st.caption(row['reference'])
                if st.form_submit_button('Save script'):
                    if narration.strip():
                        row['narration'] = narration
                        invalidate(row)
                        save('Guided scene script edited')
                        st.rerun()
                    else:
                        st.error('Enter narration for this scene.')

    elif step == 2:
        st.write('Choose a narration voice or an AI presenter voice.')
        cloud = project.get('avatar', {}).get('provider') == 'heygen'
        mode = st.radio('Voice option', ['Computer voice', 'AI presenter voice (HeyGen)'], index=1 if cloud else 0, horizontal=True)
        if mode == 'Computer voice':
            st.caption('Uses installed Windows voices. The video will show demonstrations unless a presenter is configured.')
            if st.button('Find available voices'):
                try:
                    st.session_state.simple_voices = installed_voices()
                except Exception as exc:
                    st.error(str(exc))
            choices = st.session_state.get('simple_voices', [])
            if choices:
                voice = st.selectbox('Narration voice', choices, format_func=lambda v:v['name'])
                if st.button('Use this voice', type='primary'):
                    settings.update(engine='Windows offline', voice=voice['id'], rate=155)
                    project.pop('avatar', None)
                    clear_reviews(project)
                    save('Computer narration voice selected')
                    st.success('Voice selected.')
            if settings.get('voice') and not cloud:
                st.caption('Saved voice: ' + settings['voice'].split('\\')[-1])
                if rows and st.button('Listen to first scene'):
                    try:
                        with st.spinner('Preparing voice preview…'):
                            st.audio(str(generate_cached(rows[0]['narration'], root, settings['engine'], settings['voice'], settings['rate'], settings.get('pronunciation'))))
                    except Exception as exc:
                        st.error(str(exc))
        else:
            config = project.get('avatar', {}) if cloud else {}
            secret = st.text_input('HeyGen API key', type='password', value=st.session_state.get('heygen_api_key', ''), key='simple_heygen_key')
            if secret.strip():
                st.session_state.heygen_api_key = secret.strip()
            with st.expander('Presenter and voice settings', expanded=not cloud):
                avatar_id = st.text_input('Presenter ID', config.get('avatar_id', heygen.DEFAULT_SCIENTIST))
                voice_id = st.text_input('Voice ID', config.get('voice_id', heygen.DEFAULT_VOICE))
                locale = st.text_input('Speech language', config.get('locale', 'en-IN'))
                st.caption('The default presenter and voice must be accessible to your API workspace.')
            consent = st.checkbox('I am authorized to use this presenter and allow narration to be sent to HeyGen using provider credits.')
            if st.button('Use AI presenter voice', type='primary', disabled=not consent or not (secret.strip() or heygen.configured())):
                updated = {**config, 'provider': 'heygen', 'avatar_id': avatar_id.strip(), 'voice_id': voice_id.strip(), 'locale': locale.strip(), 'cloud_authorized': True}
                if voice_id.strip() != config.get('voice_id'):
                    updated.pop('native_voice_clone', None)
                    updated.pop('voice_consent', None)
                project['avatar'] = updated
                project.pop('presenter', None)
                for row in rows:
                    if row['layout'] == 'Demonstration full screen':
                        row['layout'] = 'Presenter side-by-side'
                clear_reviews(project)
                save('Guided AI presenter and voice selected')
                st.success('Presenter and voice selected.')
        with st.expander('Use a voice from your own video or audio'):
            from .voice_clone_workspace import controls
            controls(project, root, save)

    elif step == 3:
        st.write('Choose the look, add scene visuals, and review each scene.')
        avatar = project.get('avatar', {})
        has_presenter = bool(avatar or project.get('presenter'))
        options = LAYOUTS if has_presenter else ['Demonstration full screen']
        initial_layout = rows[0]['layout'] if rows and rows[0]['layout'] in options else options[0]
        layout = st.selectbox('Video layout', options, index=options.index(initial_layout))
        production = settings.setdefault('production', {})
        production['brand'] = st.text_input('Organization name (optional)', production.get('brand', ''))
        production['burn_captions'] = st.checkbox('Show captions on the video', value=production.get('burn_captions', True))
        production.setdefault('caption_style', 'High contrast')
        production.setdefault('accent', '#246b50')
        production.setdefault('transition', 'Fade')
        settings.setdefault('preset', '720p landscape')
        for row in rows:
            if row['layout'] != layout:
                row['layout'] = layout
                invalidate(row)
        st.caption('Design changes apply to all scenes and save automatically.')
        state = jobs.status(Path(project['active_visual_job'])) if project.get('active_visual_job') else None
        busy = bool(state and state['state'] in ('queued', 'running'))
        if st.button('Create visuals for all scenes', type='primary', disabled=not rows or busy):
            project['active_visual_job'] = str(jobs.start({'task': 'generate_visuals', 'scenes': rows, 'sop_id': project['sop_id'],
                'revision': project['metadata'].get('revision', ''), 'mode': 'Animation', 'template': 'Automatic'}))
            save('Guided scene visual generation started')
            st.rerun()
        @st.fragment(run_every=2)
        def visual_status():
            current = st.session_state.project
            if not current.get('active_visual_job'):
                return
            folder = Path(current['active_visual_job'])
            state = jobs.status(folder)
            st.caption('Visuals: ' + state['state'])
            if state['state'] in ('queued', 'running'):
                st.progress(state.get('progress', 0))
                if st.button('Cancel creating visuals'):
                    jobs.cancel(folder)
            elif state['state'] == 'complete' and current.get('applied_visual_job') != str(folder):
                for item in state['results']:
                    row = next((r for r in current['scenes'] if r['scene_id'] == item['scene_id']), None)
                    if row and item['record']['generation']['scene_content_hash'] == visual_content_hash(row):
                        current['scene_assets'][row['scene_id']] = item['record']
                        invalidate(row)
                current['applied_visual_job'] = str(folder)
                save('Guided visuals attached as drafts')
                st.rerun()
            elif state['state'] not in ('complete', 'queued', 'running'):
                st.error(state.get('error', 'Visual generation interrupted.'))
        visual_status()
        if rows:
            scene_labels = [f'{"✓" if is_approved(row) else "○"} Scene {i+1}' for i, row in enumerate(rows)]
            selected = st.selectbox('Review scene', range(len(rows)), format_func=lambda i:scene_labels[i], key='simple_review_scene')
            row = rows[selected]
            st.write(row['narration'])
            with st.expander('Original SOP instruction'):
                st.write(row['original_instruction'])
                st.caption(row['reference'])
            record = scene_asset(project, row)
            if record and Path(record['path']).is_file():
                (st.image if Path(record['path']).suffix.lower() in ('.png', '.jpg', '.jpeg') else st.video)(record['path'])
            else:
                st.info('Create scene visuals above, or add your own using advanced media tools.')
            reviewer = st.text_input('Your reviewer name', key='simple_reviewer')
            notes = st.text_input('Review notes', key='simple_review_notes_' + row['scene_id'])
            confirmed = st.checkbox('I checked this scene’s narration and visual against the SOP.', key='simple_checked_' + digest(row))
            if st.button('Approve this scene', disabled=not record or not reviewer.strip() or not notes.strip() or not confirmed):
                try:
                    if not asset_current(record, row, project):
                        raise ValueError('The visual is outdated. Create visuals again.')
                    current_hash = hashlib.sha256(project['source_text'].encode()).hexdigest()
                    if row['original_instruction'] not in project['source_text'] or project['metadata'].get('storyboard_source_hash', current_hash) != current_hash:
                        raise ValueError('The SOP changed. Generate content again before review.')
                    from .editing import validate_cues
                    validate_cues(row.get('phrase_cues', []))
                    if any(c.get('asset') and not asset_current(c['asset'], row, project) for c in row.get('phrase_cues', [])):
                        raise ValueError('A phrase visual is outdated. Correct it in the advanced scene editor.')
                    record = library.review(record, reviewer, notes)
                    project['scene_assets'][row['scene_id']] = record
                    row.update(media=record['path'], media_sha256=file_hash(record['path']), source_text_sha256=current_hash,
                        presenter_sha256=file_hash(project['presenter']) if project.get('presenter') else '',
                        generation=record.get('generation'), asset_review={k:record.get(k) for k in ('asset_id', 'status', 'reviewer', 'review_notes', 'sha256')})
                    approve(row, reviewer, notes)
                    save('Guided scene and visual reviewed')
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            st.caption(f'{sum(is_approved(r) for r in rows)} of {len(rows)} scenes approved')
        with st.expander('More design options'):
            if st.button('Open advanced presenter settings', on_click=navigate, args=('Presenter studio',)):
                st.rerun()
            if st.button('Open scene preview and phrase timing', on_click=navigate, args=('Storyboard & script',)):
                st.rerun()
            st.button('Upload my own scene media', on_click=navigate, args=('Presenter & media',))

    else:
        st.write('Check your video is ready, then generate and download it.')
        preset = st.selectbox('Video size', list(PRESETS), index=list(PRESETS).index(settings.get('preset', '720p landscape')))
        settings['preset'] = preset
        strict = st.checkbox('Require reviewed visuals for every scene', value=True)
        issues = readiness(project, is_approved, strict)
        mapping = {'Source document': 1 if project['source_text'].strip() else 0, 'Voice studio': 2, 'Visual generation': 3, 'QA review': 3, 'Storyboard & script': 1}
        for index, (target, scene, message) in enumerate(issues):
            a, b = st.columns([5, 1])
            a.write(message)
            if target == 'Presenter studio':
                b.button('Fix', key=f'simple_fix_{index}', on_click=navigate, args=(target,))
            else:
                b.button('Fix', key=f'simple_fix_{index}', on_click=go, args=(mapping.get(target, 3),))
        if not issues:
            st.success('Ready to generate your training video.')
        state = jobs.status(Path(project['active_job'])) if project.get('active_job') else None
        busy = bool(state and state['state'] in ('queued', 'running'))
        permission = st.checkbox('Generate this video. If a cloud presenter is selected, send narration to that provider and use provider credits.')
        if st.button('Generate final training video', type='primary', disabled=bool(issues) or busy or not permission):
            try:
                request = {'rows': copy.deepcopy(rows), 'title': project['title'], 'engine': settings['engine'], 'voice': settings['voice'], 'rate': settings['rate'],
                    'presenter_path': project.get('presenter'), 'preset': preset, 'fps': 30, 'strict_media': strict,
                    'pronunciation_map': settings.get('pronunciation', {}), 'avatar': project.get('avatar'), 'production': settings.get('production', {}),
                    'metadata': {**project['metadata'], 'sop_id': project['sop_id'], 'project_id': project['project_id'],
                                 'current_source_text_sha256': hashlib.sha256(project['source_text'].encode()).hexdigest(), 'history': project['history'],
                                 'assets': project['assets'], 'scene_assets': project.get('scene_assets', {})}}
                key = {'heygen':'HEYGEN_API_KEY', 'synthesia':'SYNTHESIA_API_KEY'}.get(project.get('avatar', {}).get('provider'))
                project['active_job'] = str(jobs.start(request, environment=credentials.environment(st.session_state, (key,))))
                save('Final training video requested in guided workflow')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        @st.fragment(run_every=2)
        def output():
            current = st.session_state.project
            if not current.get('active_job'):
                return
            folder = Path(current['active_job'])
            state = jobs.status(folder)
            st.progress(state.get('progress', 0), text='Video: ' + state['state'])
            if state['state'] in ('queued', 'running'):
                if st.button('Cancel video generation'):
                    jobs.cancel(folder)
            elif state['state'] == 'complete':
                current['last_files'] = state['files']
                video, captions, manifest = map(Path, state['files'])
                st.video(str(video))
                st.download_button('Download training video', video.read_bytes(), video.name, 'video/mp4', type='primary')
                st.download_button('Download captions', captions.read_bytes(), captions.name)
                st.caption('Watch the full video before sharing it for training.')
            else:
                st.error(state.get('error', 'Generation interrupted.'))
        output()

    st.divider()
    back, next_col = st.columns(2)
    back.button('← Previous step', disabled=step == 0, on_click=go, args=(step-1,), width='stretch')
    ready = bool(project['source_text'].strip()) if step == 0 else bool(rows) if step == 1 else bool(settings.get('voice') or project.get('avatar')) if step == 2 else True
    next_col.button('Continue →', disabled=step == 4 or not ready, on_click=go, args=(step+1,), width='stretch')
