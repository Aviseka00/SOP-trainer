"""Unified scene production controls, shared with the storyboard editor."""
import json
from pathlib import Path
import streamlit as st
from . import jobs
from .schema import approve, invalidate, file_hash, digest
from .media import scene_asset, asset_current
from .speech import generate_cached
from .editing import validate_cues

def controls(project, row, root, library, settings, is_approved, save):
    token = row['scene_id']
    record = scene_asset(project, row)
    with st.expander('Choose a reviewed scene visual'):
        available = [a for a in library.records() if a.get('status') == 'approved' and asset_current(a, row, project)]
        if available:
            chosen = st.selectbox('Reviewed visuals for this SOP revision', available,
                                  format_func=lambda a: a['description'], key='scene_media_' + token)
            if st.button('Attach visual to this scene', key='attach_visual_' + token):
                project.setdefault('scene_assets', {})[token] = chosen
                invalidate(row)
                save('Scene visual changed; approval reset')
                st.rerun()
        else:
            st.info('Generate or register a visual and complete its technical review in Visual generation or Presenter & media.')
    st.markdown('**Audio and composed scene preview**')
    audio_key = 'audition_' + token
    signature = digest({'text': row['narration'], 'settings': settings})
    if st.button('Audition scene audio', key='audio_' + token, disabled=not settings.get('voice')):
        try:
            with st.spinner('Generating scene audio…'):
                path = generate_cached(row['narration'], root, settings['engine'], settings['voice'], settings['rate'], settings.get('pronunciation'))
            st.session_state[audio_key] = (signature, str(path))
        except Exception as exc:
            st.error(str(exc))
    audition = st.session_state.get(audio_key)
    if audition and audition[0] == signature:
        st.audio(audition[1])
        words_path = Path(audition[1] + '.words.json')
        if words_path.exists() and st.button('Build phrase cues from voice word timings', key='word_cues_' + token):
            try:
                words = json.loads(words_path.read_text(encoding='utf-8'))
                cues, chunk = [], []
                for word in words:
                    chunk.append(word)
                    if len(chunk) >= 8 or word['text'].endswith(('.', '!', '?', ';')):
                        cues.append({'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'text': ' '.join(w['text'] for w in chunk)})
                        chunk = []
                if chunk:
                    cues.append({'start': chunk[0]['start'], 'end': chunk[-1]['end'], 'text': ' '.join(w['text'] for w in chunk)})
                validate_cues(cues)
                row['phrase_cues'] = cues
                row['phrase_timing_source'] = 'TTS word boundaries; review required'
                invalidate(row)
                save('Phrase cues built from actual voice boundaries; review required')
                st.session_state.generation += 1
                st.rerun()
            except (ValueError, KeyError) as exc:
                st.error(str(exc))
    st.caption('Preview uses the selected local voice and composition. It is a draft and does not grant approval. Cloud presenter generation is performed during export.')
    if st.button('Render this scene preview', key='preview_' + token, disabled=not settings.get('voice')):
        try:
            import copy
            draft = copy.deepcopy(row)
            draft['media'] = record['path'] if record else ''
            draft.pop('media_sha256', None)
            draft.pop('presenter_sha256', None)
            approve(draft, 'Draft preview only')
            folder = jobs.start({'rows': [draft], 'title': 'DRAFT PREVIEW · ' + project['title'],
                                 'engine': settings['engine'], 'voice': settings['voice'], 'rate': settings['rate'],
                                 'presenter_path': project.get('presenter'), 'strict_media': False,
                                 'pronunciation_map': settings.get('pronunciation', {}),
                                 'production': settings.get('production', {}),
                                 'metadata': {**project['metadata'], 'sop_id': project['sop_id']}})
            st.session_state['scene_preview_' + token] = (digest(row), str(folder))
        except Exception as exc:
            st.error(str(exc))
    @st.fragment(run_every=2)
    def preview_status():
        preview = st.session_state.get('scene_preview_' + token)
        if not preview:
            return
        state = jobs.status(Path(preview[1]))
        if preview[0] != digest(row):
            st.warning('Scene changed since this preview. Render a new preview.')
        st.caption('Scene preview: ' + state['state'])
        if state['state'] == 'complete':
            st.video(state['files'][0])
        elif state['state'] in ('queued', 'running'):
            st.progress(state.get('progress', 0))
            if st.button('Cancel scene preview', key='cancel_preview_' + token):
                jobs.cancel(Path(preview[1]))
        else:
            st.error(state.get('error', 'Preview interrupted.'))
    preview_status()
    with st.expander('Phrase captions and visual timing'):
        st.caption('Listen to the audio, then enter measured start/end seconds. Cues replace scene captions. Gaps keep the base visual. Times are checked against audio at render time; no estimated word alignment is used.')
        st.caption('Phrase visual switching supports demonstration full screen and presenter side-by-side. Caption timing works with every layout.')
        cues = row.get('phrase_cues', [])
        data = [{k: c[k] for k in ('start', 'end', 'text')} for c in cues]
        edited = st.data_editor(data or [{'start': 0.0, 'end': 1.0, 'text': ''}], num_rows='dynamic',
                                key='cues_' + token + '_' + str(st.session_state.generation), hide_index=True,
                                column_config={'start': st.column_config.NumberColumn('Start (seconds)', min_value=0, step=.1),
                                               'end': st.column_config.NumberColumn('End (seconds)', min_value=0, step=.1)})
        choices = [None] + [a for a in library.records() if a.get('status') == 'approved' and asset_current(a, row, project)]
        selected_assets = []
        for i, entry in enumerate(edited):
            old = cues[i].get('asset') if i < len(cues) else None
            index = next((j for j, a in enumerate(choices) if a and old and a['asset_id'] == old['asset_id']), 0)
            selected_assets.append(st.selectbox(f'Phrase {i+1} visual', choices, index=index,
                format_func=lambda a: a['description'] if a else 'Keep scene visual', key=f'cue_asset_{token}_{i}_{st.session_state.generation}'))
        if st.button('Save phrase cues', key='save_cues_' + token):
            try:
                new = [{**c, 'asset': a} for c, a in zip(edited, selected_assets) if str(c.get('text') or '').strip()]
                validate_cues(new)
                row['phrase_cues'] = new
                row['phrase_timing_source'] = 'manual audio review'
                invalidate(row)
                save('Phrase timing changed; scene needs review')
                st.session_state.generation += 1
                st.rerun()
            except (ValueError, TypeError) as exc:
                st.error(str(exc))
    st.markdown('**Scene approval**')
    st.caption('Approved for current content' if is_approved(row) else 'Review required')
    reviewer = st.text_input('Scene reviewer', key='scene_reviewer_' + token)
    confirmed = st.checkbox('I checked the source, narration, visual, pronunciation and phrase timing.', key='scene_confirm_' + token)
    import hashlib
    source_hash = hashlib.sha256(project['source_text'].encode()).hexdigest()
    traceable = bool(project['source_text'].strip() and row['original_instruction'] in project['source_text'] and project['metadata'].get('storyboard_source_hash', source_hash) == source_hash)
    valid_media = not record or asset_current(record, row, project)
    for cue in row.get('phrase_cues', []):
        if cue.get('asset') and not asset_current(cue['asset'], row, project):
            valid_media = False
    if not traceable or not valid_media:
        st.warning('Approval is blocked until source traceability and attached visual applicability are restored.')
    if st.button('Approve scene here', key='approve_' + token, disabled=not reviewer.strip() or not confirmed or not traceable or not valid_media):
        try:
            row.update(media=record['path'] if record else '', media_sha256=file_hash(record['path']) if record else '',
                       source_text_sha256=source_hash, presenter_sha256=file_hash(project['presenter']) if project.get('presenter') else '',
                       generation=record.get('generation') if record else None,
                       asset_review={k: record.get(k) for k in ('asset_id', 'status', 'reviewer', 'review_notes', 'sha256')} if record else None)
            approve(row, reviewer, row.get('review_comments', ''))
            save('Scene approved in unified editor')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
