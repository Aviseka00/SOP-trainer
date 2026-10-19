"""Streamlit workspace. All rendering is performed by a separate worker process."""
from __future__ import annotations
import asyncio
import hashlib
import html
import json
import uuid
from pathlib import Path
import streamlit as st
from engine import ROOT, CATEGORIES, LAYOUTS, extract, storyboard
from sop_studio.schema import validate_project, approve, invalidate, file_hash, digest, scene_fingerprint
from sop_studio.ingestion import metadata, source_record, contradiction_flags
from sop_studio.storage import ProjectStore
from sop_studio.media import MediaLibrary, safe_media, scene_asset, asset_current, visual_content_hash
from sop_studio.visuals import TEMPLATES
from sop_studio.composition import PRESETS
from sop_studio.speech import installed_voices, edge_voices, generate_cached
from sop_studio import jobs, llm
from sop_studio.summary import build_brief, polish_brief, brief_current, brief_scenes, source_hash
from sop_studio import heygen, synthesia, kling, credentials
from sop_studio.diagnostics import diagnose
from sop_studio.theme import apply
from sop_studio.editing import WORKFLOW, content_digest, readiness, validate_cues
from sop_studio.simple_workflow import STEPS as SIMPLE_STEPS, go as simple_go

st.set_page_config(page_title='SOP Trainer AI | Production workspace', page_icon='◈', layout='wide')
apply()
store = ProjectStore(ROOT / 'projects')
library = MediaLibrary(ROOT / 'approved_media')

def new_project():
    return validate_project({'title': 'Untitled training', 'scenes': [], 'source_text': '', 'sop_id': '',
                             'metadata': {'revision': '', 'effective_date': ''}, 'assets': {},
                             'settings': {'engine': 'Windows offline', 'voice': '', 'rate': 155, 'language': 'en-US',
                                          'preset': '720p landscape', 'pronunciation': {}}})

if 'project' not in st.session_state:
    st.session_state.project = new_project()
if 'generation' not in st.session_state:
    st.session_state.generation = 0
credential_file = ROOT/'.local'/'credentials.dpapi'
credential_stamp = credential_file.stat().st_mtime_ns if credential_file.exists() else 0
if not st.session_state.get('_provider_keys_loaded') or st.session_state.get('_provider_keys_stamp') != credential_stamp:
    try:
        for name,value in credentials.load(ROOT).items():
            key = credentials.SESSION_NAMES[name]
            if not st.session_state.get(key):
                st.session_state[key] = value
                st.session_state.pop('provider_'+key,None)
                if key == 'heygen_api_key':
                    st.session_state.pop('heygen_key_input',None)
    except (RuntimeError, ValueError, OSError):
        st.session_state.provider_key_notice = 'Saved provider keys could not be unlocked. Re-enter them in AI providers.'
    st.session_state._provider_keys_loaded = True
    st.session_state._provider_keys_stamp = credential_stamp

def load_project(data, imported=False):
    project = validate_project(data)
    project.setdefault('settings', new_project()['settings'])
    if imported:
        project['project_id'] = uuid.uuid4().hex
        project['assets'] = {}
        project['scene_assets'] = {}
        project.pop('active_visual_job', None)
        project.pop('avatar', None)
        project.pop('avatar_preview_job', None)
        project.pop('presenter', None)
        project.pop('active_job', None)
        project.pop('last_files', None)
        project.pop('cloud_audition', None)
        project.pop('presenter_quality_review', None)
        project.pop('voice_sample', None)
        project.pop('voice_clone', None)
        for row in project['scenes']:
            row['media'] = ''
            for cue in row.get('phrase_cues', []):
                cue.pop('asset', None)
            invalidate(row)
        project['history'].append({'reason': 'Imported JSON: media must be reattached and all scenes reviewed.'})
    else:
        for topic, record in list(project['assets'].items()):
            try:
                safe_media(record['path'], ROOT / 'approved_media')
            except (ValueError, KeyError, TypeError):
                del project['assets'][topic]
        for scene_id, record in list(project.get('scene_assets', {}).items()):
            try:
                safe_media(record['path'], ROOT / 'approved_media')
            except (ValueError, KeyError, TypeError):
                del project['scene_assets'][scene_id]
    st.session_state.project = project
    st.session_state.generation += 1
    st.session_state._saved_digest = content_digest(project) if not imported else ''

def save(reason='Project saved'):
    st.session_state.project = store.save(st.session_state.project, st.session_state.get('reviewer', '') or 'local operator', reason)
    st.session_state._saved_digest = content_digest(st.session_state.project)

def navigate(target, scene=None):
    st.session_state._next_page = target
    if scene is not None:
        st.session_state._next_scene = scene

if not st.session_state.get('_simple_ui_initialized'):
    st.session_state._simple_ui_initialized = True
    st.session_state.setdefault('_next_page', 'Create training')
if '_next_page' in st.session_state:
    st.session_state.workspace_page = st.session_state.pop('_next_page')

def reset_approvals():
    for row in st.session_state.project['scenes']:
        invalidate(row)

def upload_media(upload, prefix):
    if upload.size > 500 * 1024**2:
        raise ValueError('Media upload limit: 500 MB.')
    checksum = hashlib.sha256(upload.getvalue()).hexdigest()
    path = ROOT / 'approved_media' / f'{prefix}_{checksum[:24]}{Path(upload.name).suffix.lower()}'
    if not path.exists():
        path.write_bytes(upload.getvalue())
    return str(path)

def bound_scene_media(row):
    record = scene_asset(st.session_state.project, row)
    return record['path'] if record else ''

def is_approved(row):
    if not row.get('approved') or row.get('review_hash') != scene_fingerprint(row):
        return False
    try:
        validate_cues(row.get('phrase_cues', []))
        if any(c.get('asset') and not asset_current(c['asset'], row, st.session_state.project) for c in row.get('phrase_cues', [])):
            return False
    except (OSError, ValueError):
        return False
    current_source = hashlib.sha256(st.session_state.project['source_text'].encode('utf-8')).hexdigest()
    if row.get('source_text_sha256') != current_source:
        return False
    presenter = st.session_state.project.get('presenter')
    if row.get('presenter_sha256', '') != (file_hash(presenter) if presenter and Path(presenter).exists() else ''):
        return False
    record = scene_asset(st.session_state.project, row)
    if row.get('media_sha256'):
        return bool(asset_current(record, row, st.session_state.project) and file_hash(record['path']) == row['media_sha256'])
    return not record

p = st.session_state.project
rows = p['scenes']
g = f'{p["project_id"]}_{st.session_state.generation}'
settings = p.setdefault('settings', new_project()['settings'])
with st.sidebar:
    st.markdown('<div class="brand">◈ SOP Trainer AI<span style="color:#6d8b68">.</span></div>', unsafe_allow_html=True)
    st.caption('CREATE YOUR TRAINING VIDEO')
    for step_index, step_label in enumerate(SIMPLE_STEPS):
        st.button(f'{step_index+1} · {step_label}', on_click=simple_go, args=(step_index,), width='stretch',
                  type='primary' if st.session_state.get('workspace_page') == 'Create training' and st.session_state.get('simple_step', 0) == step_index else 'secondary')
    with st.expander('Advanced tools'):
        page = st.radio('Workspace', ['Create training', 'Dashboard', 'Source document', 'Summary & key points', 'Storyboard & script', 'Presenter & media', 'Visual generation', 'Presenter studio', 'AI providers', 'Voice studio', 'Timeline', 'QA review', 'Export center', 'Models & diagnostics'], label_visibility='collapsed', key='workspace_page')
    st.divider()
    if st.button('Save to workspace', width='stretch'):
        save()
        st.success('Saved locally with a version snapshot.')
    st.caption('Saved · ' + p.get('saved_at', 'new project') if content_digest(p) == st.session_state.get('_saved_digest') else 'Changes will autosave after this interaction')
    with st.expander('Recover a previous version'):
        versions = store.versions(p['project_id'])
        if versions:
            version = st.selectbox('Snapshot', versions, format_func=lambda v: f"{v['saved_at']} · {v['scenes']} scenes · {v['version'][:8]}")
            st.caption('Restoring keeps the current version in history. Changed or missing media must be reviewed again.')
            if st.button('Restore selected snapshot'):
                load_project(store.restore(p['project_id'], version['version']))
                st.rerun()
        else:
            st.caption('Snapshots appear after the next saved change.')
    available = store.list()
    with st.expander('Open local project'):
        if available:
            project_id = st.selectbox('Saved projects', [x['project_id'] for x in available], format_func=lambda x: next(a['title'] for a in available if a['project_id'] == x))
            if st.button('Open selected project'):
                load_project(store.load(project_id))
                st.rerun()
        else:
            st.caption('No saved projects yet.')
        upload = st.file_uploader('Import storyboard JSON', type=['json'])
        if st.button('Import as new draft', disabled=upload is None):
            try:
                if upload.size > 10 * 1024**2:
                    raise ValueError('JSON limit: 10 MB.')
                load_project(json.loads(upload.getvalue()), imported=True)
                st.rerun()
            except (ValueError, TypeError, KeyError) as exc:
                st.error(str(exc))
    st.download_button('↓ Download project JSON', json.dumps(p, ensure_ascii=False, indent=2), 'sop-project.json', 'application/json', width='stretch')
    st.caption('Save locally to retain media associations. JSON imports open as new drafts with media detached.')

st.markdown(f'<div class="eyebrow">Production workspace / {html.escape(page)}</div>', unsafe_allow_html=True)
st.title(p['title'] if p['title'] != 'Untitled training' else 'Good procedures. Great training.')
if page in WORKFLOW:
    step = WORKFLOW.index(page)
    st.progress((step+1)/len(WORKFLOW), text=f'Step {step+1} of {len(WORKFLOW)} · {page}')
    back, _, forward = st.columns([1, 3, 1])
    back.button('← Back', disabled=step == 0, on_click=navigate, args=(WORKFLOW[max(0, step-1)],), width='stretch')
    forward.button('Next →', disabled=step == len(WORKFLOW)-1, on_click=navigate, args=(WORKFLOW[min(len(WORKFLOW)-1, step+1)],), width='stretch')
st.caption(f'{p["sop_id"] or "No SOP number"}  ·  Revision {p["metadata"].get("revision") or "not specified"}  ·  Local project {p["project_id"][:8]}')

if page == 'Create training':
    from sop_studio.simple_workflow import render as render_simple_workflow
    render_simple_workflow(p, ROOT, store, library, save, load_project, new_project, is_approved, navigate)

elif page == 'Dashboard':
    recent = store.list()
    if recent and not rows:
        st.info('Resume your latest saved project: ' + recent[0]['title'])
        if st.button('Resume latest project'):
            load_project(store.load(recent[0]['project_id']))
            st.rerun()
    actual_demo=ROOT/'examples/cloud_acceptance/SOP_Cloud_Scientist_Demo.mp4'
    if actual_demo.is_file():
        with st.expander('Watch the completed cloud scientist test'):
            st.video(str(actual_demo))
            st.caption('Eight source-linked cloud presenter scenes with local contextual animations. Original cloud speech retained; measured compositor-added audio offset was 0 ms at 2 ms resolution. Sample SOP only; exact phoneme and gesture accuracy is not certified.')
    approved_count = sum(is_approved(r) for r in rows)
    for col, label, value in zip(st.columns(4), ['Storyboard scenes', 'Reviewed & ready', 'Estimated narration', 'Attached visuals'], [len(rows), f'{approved_count} / {len(rows)}', f'{sum(len(r["narration"].split()) for r in rows) / 155:.1f} min', len(p['assets'])+len(p.get('scene_assets', {}))]):
        col.metric(label, value)
    st.markdown('<div class="hero"><span class="tag">FROM PROCEDURE TO PRACTICE</span><h2>Clarity at every step.</h2><p>Bring your approved procedure. Review the story, pair it with the right demonstration, and produce a traceable training video.</p></div>', unsafe_allow_html=True)
    a, b = st.columns([1.4, 1])
    with a:
        st.subheader('Your production path')
        st.markdown('**01 · Source document** — upload your SOP.\n\n**02 · Summary & key points** — draft and review source-linked speech.\n\n**03 · Visual generation** — build and inspect contextual animations.\n\n**04 · Presenter studio** — select the fictional scientist and voice.\n\n**05 · QA review & export** — approve scenes, render, and inspect playback.')
        if rows:
            st.progress(approved_count / len(rows), text='Scene review progress')
    with b:
        st.subheader('Capability status')
        st.write('✓ Source-preserving planning and local project history')
        st.write('✓ Recorded presenter composition and CPU video export')
        st.write('○ Optional Ollama explanations require an installed model')
        st.write('✓ Automatic local schematic illustrations and animations')
        st.write('○ AI facial animation is optional; check setup status in Presenter studio')
        st.caption('No regulatory validation is claimed. Estimated duration uses 155 words/minute; rendering measures actual audio.')
    if st.button('Explore the hand-hygiene example'):
        project = new_project()
        project['source_text'] = (ROOT / 'examples' / 'hand_hygiene.txt').read_text(encoding='utf-8')
        project['metadata'] = metadata(project['source_text'])
        project['title'] = project['metadata']['title']
        project['sop_id'] = project['metadata']['sop_number']
        project['scenes'] = storyboard(project['source_text'])
        load_project(project)
        save('Example project created; not an approved procedure')
        st.rerun()

elif page == 'Source document':
    st.subheader('Start with the effective source')
    with st.form(f'source_{g}'):
        title = st.text_input('Training title', p['title'])
        c1, c2, c3 = st.columns(3)
        sop_id = c1.text_input('SOP number', p['sop_id'])
        revision = c2.text_input('Revision', p['metadata'].get('revision', ''))
        effective = c3.text_input('Effective date', p['metadata'].get('effective_date', ''))
        text = st.text_area('Source text', p['source_text'], height=320)
        st.caption('Updating source information invalidates every scene approval. Rebuild the storyboard explicitly to replace old instructions.')
        if st.form_submit_button('Save source information', type='primary'):
            old = digest([p['title'], p['sop_id'], p['source_text'], p['metadata'].get('revision'), p['metadata'].get('effective_date')])
            p.update(title=title, sop_id=sop_id, source_text=text)
            p['metadata'].update(revision=revision, effective_date=effective)
            if old != digest([title, sop_id, text, revision, effective]):
                reset_approvals()
            save('Source information updated')
            st.rerun()
    upload = st.file_uploader('Import PDF, DOCX or TXT (25 MB maximum)', type=['pdf', 'docx', 'txt'])
    if st.button('Extract and retain original source', disabled=upload is None):
        try:
            text = extract(upload.name, upload.getvalue())
            record = source_record(upload.name, upload.getvalue(), text)
            source_path = store.folder(p['project_id']) / 'sources' / (record['sha256'] + Path(upload.name).suffix.lower())
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_bytes(upload.getvalue())
            p.update(source_text=text, title=record['title'] or p['title'], sop_id=record['sop_number'] or p['sop_id'])
            p['metadata'].update(record, source_path=str(source_path))
            reset_approvals()
            st.session_state.generation += 1
            save('Source document imported')
            st.rerun()
        except Exception as exc:
            st.error(f'Import failed: {exc}')
    auto_visuals = st.checkbox('Automatically create contextual animations when building the storyboard', value=True)
    st.info('For an overview video, open Summary & key points after saving or uploading your SOP. Generate a draft, review the speech, then build animations from those points.')
    if st.button('Build traceable storyboard →', type='primary', disabled=not p['source_text'].strip()):
        try:
            p['scenes'] = storyboard(p['source_text'])
            p['metadata']['storyboard_source_hash'] = hashlib.sha256(p['source_text'].encode('utf-8')).hexdigest()
            if auto_visuals:
                p['active_visual_job'] = str(jobs.start({'task':'generate_visuals', 'scenes':p['scenes'],
                    'sop_id':p['sop_id'], 'revision':p['metadata'].get('revision', ''), 'mode':'Animation', 'template':'Automatic'}))
            st.session_state.generation += 1
            save('Storyboard rebuilt from source; all scenes draft')
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.caption('Rebuilding replaces existing scenes. Previous saved versions are retained in the project history directory. Numbered steps remain intact; metadata and headings are included for reviewer decisions.')
    if p.get('active_visual_job'):
        st.info('Automatic visual job created. Open Visual generation to monitor, attach and review its results.')
    if p['metadata'].get('sha256'):
        st.code('Original document SHA-256: ' + p['metadata']['sha256'])

elif page == 'Summary & key points':
    st.subheader('Turn your SOP into a clear training overview')
    st.caption('1 · Upload in Source document   →   2 · Review summary and speech   →   3 · Build contextual animations   →   4 · Select scientist and render')
    target = st.slider('Target key points', 3, 30, 8)
    if st.button('Generate summary & speech draft', type='primary', disabled=not p['source_text'].strip()):
        try:
            p['training_brief'] = build_brief(p['source_text'], target)
            st.session_state.generation += 1
            save('Source-linked training overview drafted')
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    brief = p.get('training_brief')
    if brief and not brief_current(brief, p['source_text']):
        st.warning('The source changed. Generate a new summary; this draft cannot build current scenes.')
    if brief and brief_current(brief, p['source_text']):
        st.info(brief['notice'])
        st.caption(f'{brief["method"]} · {len(brief["points"])} points · {brief["omitted_segments"]} source segments omitted from this overview')
        with st.expander('Optional local AI speech rewrite'):
            st.caption('Requires an installed Ollama model. Rewrites the selected source points; retains source links and requires comparison before use.')
            model = st.text_input('Installed Ollama model name', key='summary_model')
            if st.button('Polish speech with local AI', disabled=not model.strip()):
                try:
                    with st.spinner('Rewriting selected points locally…'):
                        p['training_brief'] = polish_brief(brief, model.strip())
                    st.session_state.generation += 1
                    save('Local AI overview rewrite drafted')
                    st.rerun()
                except (RuntimeError, ValueError) as exc:
                    st.error(str(exc))
        edited = []
        with st.form(f'brief_{g}'):
            for i, point in enumerate(brief['points']):
                st.markdown(f'**{i+1} · {point["topic"]}** — {point["source_reference"]}')
                st.caption('Source: '+point['original_instruction'])
                key_point = st.text_input('Key point', point['key_point'], key=f'kp_{g}_{i}')
                speech = st.text_area('Speech for this point', point['speech'], key=f'speech_{g}_{i}')
                visual = st.text_input('Context for animation', point['visual_description'], key=f'visual_{g}_{i}')
                edited.append({**point, 'key_point':key_point, 'speech':speech, 'visual_description':visual})
            if st.form_submit_button('Save summary and speech'):
                if any(not x['speech'].strip() or not x['key_point'].strip() for x in edited):
                    st.error('Each point needs a key point and speech.')
                else:
                    brief.update(points=edited, review_status='draft')
                    st.session_state.generation += 1
                    save('Training overview edited; rebuild scenes to apply changes')
                    st.rerun()
        speech_text = '\n\n'.join(x['speech'] for x in brief['points'])
        st.download_button('Download speech draft', speech_text, 'training-speech.txt', 'text/plain')
        st.download_button('Download source-linked key points', json.dumps(brief, ensure_ascii=False, indent=2), 'training-brief.json', 'application/json')
        accepted = st.checkbox('I compared the summary speech with the SOP and accept the overview omissions.')
        if st.button('Build scenes & contextual animations →', type='primary', disabled=not accepted):
            try:
                p['scenes'] = brief_scenes(brief, p['source_text'])
                p['scene_assets'] = {}
                p['metadata']['storyboard_source_hash'] = source_hash(p['source_text'])
                p['active_visual_job'] = str(jobs.start({'task':'generate_visuals', 'scenes':p['scenes'], 'sop_id':p['sop_id'],
                    'revision':p['metadata'].get('revision',''), 'mode':'Animation', 'template':'Automatic'}))
                brief['review_status'] = 'accepted for storyboard; scene review pending'
                st.session_state.generation += 1
                save('Summary scenes and contextual animation job created')
                st.success('Scenes created. Open Visual generation to review animations, Presenter studio to select the scientist, then QA review and Export center.')
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

elif page == 'Storyboard & script':
    if not rows:
        st.info('Create a storyboard from Source document first.')
    else:
        selected = st.selectbox('Scene', range(len(rows)), index=min(st.session_state.pop('_next_scene', 0), len(rows)-1), format_func=lambda i:f'{i+1:02} · {rows[i]["reference"]} · {rows[i]["visual"]}')
        row = rows[selected]
        a, b = st.columns([1.2, 1], gap='large')
        with a:
            st.subheader('Shape the narration')
            with st.container():
                narration = st.text_area('Spoken narration', row['narration'], height=180)
                topic = st.selectbox('Visual topic', list(CATEGORIES)+['General'], index=(list(CATEGORIES)+['General']).index(row['visual']))
                layout = st.selectbox('Composition', LAYOUTS, index=LAYOUTS.index(row['layout']))
                reference = st.text_input('SOP reference', row['reference'])
                description = st.text_area('Visual description', row['visual_description'])
                comments = st.text_area('Review comments', row['review_comments'])
                changed = any(row.get(k) != v for k, v in dict(narration=narration, visual=topic, layout=layout, reference=reference, visual_description=description, review_comments=comments).items())
                explicit_save = st.button('Save scene changes', type='primary')
                if changed or explicit_save:
                    if not narration.strip():
                        st.error('Narration cannot be empty.')
                    else:
                        row.update(narration=narration, visual=topic, layout=layout, reference=reference, visual_description=description, review_comments=comments)
                        invalidate(row)
                        save(f'Scene {selected+1} edited; approval invalidated')
                        st.rerun()
            scene_visual = scene_asset(p, row)
            if scene_visual and Path(scene_visual['path']).is_file():
                st.caption('Scene-specific visual preview · ' + scene_visual['status'])
                if Path(scene_visual['path']).suffix.lower() in ('.png', '.jpg', '.jpeg'):
                    st.image(scene_visual['path'], width='stretch')
                else:
                    st.video(scene_visual['path'])
            if st.button('Remove this scene from narration', key=f'remove_scene_{row["scene_id"]}'):
                rows.pop(selected)
                st.session_state.generation += 1
                save(f'Scene {selected+1} removed from narration; original source retained')
                st.rerun()
        with b:
            st.subheader('Source & preview')
            st.markdown(f'<div class="preview"><small>Scene {selected+1:02} · {html.escape(row["safety_classification"])}</small><h3>{html.escape(row["visual"])}</h3><p>{html.escape(row["narration"])}</p></div>', unsafe_allow_html=True)
            st.markdown('**Original instruction — retained verbatim**')
            st.write(row['original_instruction'])
            from sop_studio.scene_workspace import controls
            controls(p, row, ROOT, library, settings, is_approved, save)
            for flag in row['flags'] + contradiction_flags(row['original_instruction'], row['narration']):
                st.warning(flag)
            st.caption('These are heuristic review flags, not proof of correctness or contradiction detection completeness.')
            if row.get('explanation'):
                st.markdown('**Optional model explanation — not automatically spoken**')
                st.write(row['explanation'])
            with st.expander('Optional local AI explanation'):
                st.caption('Requires Ollama on 127.0.0.1:11434 and a model you installed. Source text stays local. Narration remains unchanged.')
                if st.button('Discover installed Ollama models'):
                    try:
                        st.session_state.ollama_models = llm.models()
                    except Exception as exc:
                        st.error(str(exc))
                choices = st.session_state.get('ollama_models', [])
                if choices:
                    model = st.selectbox('Local model', choices)
                    if st.button('Generate reviewable explanation'):
                        try:
                            with st.spinner('Running local model…'):
                                rows[selected] = llm.enrich_scene(row, model)
                            save('Local model explanation added; scene requires review')
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

elif page == 'Presenter & media':
    st.subheader('Context comes from reviewed demonstrations')
    st.info('Recorded presenters are shown silently and looped. This does not generate facial motion or lip-sync.')
    presenter = st.file_uploader('Recorded presenter video', type=['mp4', 'mov', 'mkv'], key=f'presenter_{g}')
    if presenter and st.button('Attach presenter recording'):
        p['presenter'] = upload_media(presenter, 'presenter')
        p.pop('avatar', None)
        reset_approvals()
        save('Presenter recording attached; scene approvals reset')
        st.rerun()
    if p.get('presenter'):
        st.caption('Attached: ' + Path(p['presenter']).name)
        if st.button('Remove presenter'):
            p.pop('presenter', None)
            reset_approvals()
            save('Presenter removed')
            st.rerun()
    topics = sorted(set(r['visual'] for r in rows)) or list(CATEGORIES)
    topic = st.selectbox('Visual topic', topics)
    record = p['assets'].get(topic)
    if record:
        st.write(f'Current asset: {record["description"] or Path(record["path"]).name} · {record["status"]}')
        if Path(record['path']).suffix.lower() in ('.png', '.jpg', '.jpeg'):
            st.image(record['path'], width=500)
        else:
            st.video(record['path'])
        if st.button('Detach topic asset'):
            del p['assets'][topic]
            for r in rows:
                if r['visual'] == topic:
                    invalidate(r)
            save('Topic asset detached')
            st.rerun()
    media = st.file_uploader('Image or demonstration video', type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'mkv', 'webm'], key=f'asset_{topic}_{g}')
    with st.form(f'asset_metadata_{topic}_{g}'):
        description = st.text_input('Asset description')
        source = st.text_input('Source / owner')
        license_value = st.text_input('License / organizational usage rights')
        reviewer = st.text_input('Technical reviewer (blank keeps asset draft)')
        notes = st.text_area('Technical review notes')
        if st.form_submit_button('Register and attach asset', disabled=media is None):
            try:
                path = upload_media(media, 'asset')
                record = library.add(path, topic, description, source, license_value, p['sop_id'], p['metadata'].get('revision', ''), reviewer, notes)
                p['assets'][topic] = record
                for r in rows:
                    if r['visual'] == topic:
                        invalidate(r)
                save('Asset registered and attached; affected scenes require review')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    matches = library.match(topic, p['sop_id'], p['metadata'].get('revision', ''))
    st.caption('Retrieval uses exact topic + SOP + revision matching in this milestone. Generated visuals are attached per scene. Semantic embeddings are not implemented.')
    if matches:
        chosen = st.selectbox('Reusable reviewed library assets', range(len(matches)), format_func=lambda i:matches[i]['description'] or matches[i]['asset_id'])
        if st.button('Use matched library asset'):
            p['assets'][topic] = matches[chosen]
            for r in rows:
                if r['visual'] == topic:
                    invalidate(r)
            save('Reviewed library asset selected')
            st.rerun()

elif page == 'Visual generation':
    st.subheader('Create the visual from the instruction')
    visual_provider = st.selectbox('Visual provider', ['Local schematics', 'Kling AI'])
    st.caption('Local schematics use the CPU. Kling generates cloud video clips and consumes provider credits. All depictions require technical review; English template labels are not automatically translated.')
    kling_options = {}
    cloud_visual_ready = True
    if visual_provider == 'Kling AI':
        st.caption('Configure a Kling developer API key in AI providers. Only the scene’s animation context is sent; the complete SOP is not uploaded.')
        model = st.selectbox('Kling model', kling.MODELS)
        clip_duration = st.selectbox('Kling clip duration (seconds)', [5,10])
        permission = st.checkbox('Send selected scene contexts to Kling AI and use my provider credits for generation.')
        cloud_visual_ready = bool(permission and (st.session_state.get('kling_api_key','').strip() or kling.configured()))
        kling_options = {'model':model, 'duration':clip_duration, 'cloud_authorized':bool(permission)}
    if not rows:
        st.info('Build a storyboard first. Automatic generation is enabled by default in Source document.')
    else:
        selected = st.selectbox('Scene to preview or regenerate', range(len(rows)), format_func=lambda i:f'{i+1:02} · {rows[i]["narration"][:85]}', key='visual_scene')
        row = rows[selected]
        st.write(row['narration'])
        mode = st.radio('Output type', ['Animation', 'Illustration'] if visual_provider == 'Local schematics' else ['Animation'], horizontal=True)
        template = st.selectbox('Visual interpretation', TEMPLATES, help='Automatic selects a diagram from the narration and visual description. Source prohibitions always produce a warning.')
        state = jobs.status(Path(p['active_visual_job'])) if p.get('active_visual_job') else None
        busy = state and state['state'] in ('queued', 'running')
        a, b = st.columns(2)
        one = a.button('Generate for this scene', type='primary', disabled=bool(busy) or not cloud_visual_ready, width='stretch')
        all_scenes = b.button('Generate for every scene', disabled=bool(busy) or not cloud_visual_ready, width='stretch')
        if one or all_scenes:
            p['active_visual_job'] = str(jobs.start({'task':'generate_visuals', 'scenes':[row] if one else rows,
                'sop_id':p['sop_id'], 'revision':p['metadata'].get('revision', ''), 'mode':mode, 'template':template,
                'provider':'kling' if visual_provider == 'Kling AI' else 'local', 'provider_config':kling_options},
                environment=credentials.environment(st.session_state, ('KLING_API_KEY',)) if visual_provider == 'Kling AI' else None))
            save('Contextual visual generation started')
            st.rerun()

        @st.fragment(run_every=2)
        def generation_status():
            project = st.session_state.project
            if not project.get('active_visual_job'):
                return
            folder = Path(project['active_visual_job'])
            state = jobs.status(folder)
            st.progress(state.get('progress', 0), text='Visual generation: ' + state['state'])
            if state['state'] in ('queued', 'running'):
                if st.button('Cancel visual generation'):
                    jobs.cancel(folder)
            elif state['state'] == 'complete':
                if project.get('applied_visual_job') != str(folder):
                    attached = 0
                    for item in state['results']:
                        scene = next((r for r in project['scenes'] if r['scene_id'] == item['scene_id']), None)
                        if scene and item['record']['generation']['scene_content_hash'] == visual_content_hash(scene):
                            project.setdefault('scene_assets', {})[scene['scene_id']] = item['record']
                            invalidate(scene)
                            attached += 1
                    project['applied_visual_job'] = str(folder)
                    save(f'Generated {attached} scene visuals attached as drafts')
                    st.rerun()
                st.success('Generated visuals attached. Preview each scene and record technical review below.')
            else:
                st.error(state.get('error', 'Visual generation interrupted.'))
                partial = folder/'visuals.partial.json'
                if partial.exists() and st.button('Attach completed visuals from interrupted job'):
                    for item in json.loads(partial.read_text(encoding='utf-8'))['results']:
                        scene = next((r for r in project['scenes'] if r['scene_id'] == item['scene_id']), None)
                        if scene and item['record']['generation']['scene_content_hash'] == visual_content_hash(scene):
                            project.setdefault('scene_assets', {})[scene['scene_id']] = item['record']
                            invalidate(scene)
                    save('Completed visuals recovered from interrupted generation')
                    st.rerun()
        generation_status()
        record = scene_asset(p, row)
        if record:
            if not asset_current(record, row, p):
                st.warning('This visual is outdated or changed. Regenerate it from the current text.')
            st.markdown('**Attached visual · ' + record['status'] + '**')
            if Path(record['path']).is_file():
                if Path(record['path']).suffix.lower() == '.png':
                    st.image(record['path'], width='stretch')
                else:
                    st.video(record['path'])
                st.download_button('Download generated visual', Path(record['path']).read_bytes(), Path(record['path']).name)
            if record.get('generation'):
                st.caption('Template: ' + record['generation']['template'] + ' · ' + record['generation']['generator'])
                with st.form(f'visual_review_{g}_{record["asset_id"]}'):
                    reviewer = st.text_input('Technical reviewer')
                    notes = st.text_area('Technical review notes', placeholder='Confirm source applicability, depiction, labels and limitations.')
                    confirmed = st.checkbox('I verified this schematic / generated clip against the effective SOP and applicable equipment documents.')
                    if st.form_submit_button('Approve generated visual', disabled=not asset_current(record, row, p)):
                        try:
                            if not confirmed:
                                raise ValueError('Confirm technical verification before approving the visual.')
                            p.setdefault('scene_assets', {})[row['scene_id']] = library.review(record, reviewer, notes)
                            invalidate(row)
                            save('Generated visual technically reviewed; narration review still required')
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            if st.button('Detach scene-specific visual'):
                p.setdefault('scene_assets', {}).pop(row['scene_id'], None)
                invalidate(row)
                save('Scene-specific visual detached; topic asset may still apply')
                st.rerun()
        else:
            st.info('No visual attached to this scene yet.')

elif page == 'Presenter studio':
    from sop_studio.quality_workspace import preparation
    preparation(p, save)
    st.caption('For Synthesia presenters and encrypted provider credentials, open AI providers. Your current presenter: '+p.get('avatar',{}).get('provider','local / not configured'))
    with st.expander('Import a cloud-rendered video for each scene'):
        st.caption('Use this for clips rendered through the chat connector or a provider website. Attach the video that speaks the exact scene narration. Its original speech is retained; changing narration requires a new matching clip.')
        if rows:
            imported_scene=st.selectbox('Scene for cloud clip',range(len(rows)),format_func=lambda i:f'{i+1}: {rows[i]["narration"][:75]}')
            selected_row=rows[imported_scene]
            st.write(selected_row['narration'])
            imported_video=st.file_uploader('Cloud presenter video with original speech',type=['mp4','mov','webm'],key=f'cloud_clip_{g}_{selected_row["scene_id"]}')
            declared_provider=st.text_input('Cloud clip provider','HeyGen')
            declared_id=st.text_input('Provider video ID (optional)')
            permitted=st.checkbox('I can use this clip and confirmed it speaks this exact narration.')
            if st.button('Attach cloud presenter to this scene',disabled=not imported_video or not permitted):
                path=upload_media(imported_video,'cloud_presenter')
                clips=dict(p.get('avatar',{}).get('clips',{})) if p.get('avatar',{}).get('provider')=='imported-cloud' else {}
                clips[digest(selected_row['narration'])]={'path':path,'sha256':file_hash(path),'provider':declared_provider,'video_id':declared_id}
                p['avatar']={'provider':'imported-cloud','cloud_authorized':True,'clips':clips}
                p.pop('presenter',None)
                for scene in rows:
                    scene['layout']='Presenter side-by-side'
                reset_approvals()
                save('Scene-bound cloud presenter imported; approvals reset')
                st.success('Attached. Add matching videos for all scenes before rendering.')
            if p.get('avatar',{}).get('provider')=='imported-cloud':
                count=sum(digest(r['narration']) in p['avatar'].get('clips',{}) for r in rows)
                st.caption(f'{count} / {len(rows)} scenes have narration-matched imported clips.')
    st.subheader('Fictional scientist with cloud speech and gestures')
    st.caption('HeyGen Avatar IV generates the speaking performance. The final scene uses that video’s own speech to preserve its timing. Gesture and gaze quality require playback review.')
    with st.expander('HeyGen cloud presenter setup', expanded=bool(p.get('avatar', {}).get('provider') == 'heygen')):
        cloud_key_input = st.text_input('HeyGen API key (this session only)', type='password', key='heygen_key_input', value=st.session_state.get('heygen_api_key',''))
        st.session_state.heygen_api_key = cloud_key_input
        cloud_key_ready = bool(st.session_state.get('heygen_api_key','').strip() or heygen.configured())
        st.write('API key: '+('available' if cloud_key_ready else 'not configured'))
        st.caption('The HeyGen connection in this chat is separate from your app. Enter an API key here, or set HEYGEN_API_KEY before starting Streamlit. Session keys stay in memory and worker environments, never in project JSON or job files. Provider API usage consumes credits.')
        cloud_config = p.get('avatar', {}) if p.get('avatar', {}).get('provider') == 'heygen' else {}
        cloud_id = st.text_input('HeyGen fictional scientist look ID', cloud_config.get('avatar_id', heygen.DEFAULT_SCIENTIST))
        cloud_voice = st.text_input('HeyGen voice ID', cloud_config.get('voice_id', heygen.DEFAULT_VOICE))
        cloud_locale = st.text_input('Speech locale', cloud_config.get('locale', 'en-IN'))
        cloud_motion = st.text_area('Scientist gesture direction', cloud_config.get('motion_prompt', heygen.MOTION))
        cloud_permission = st.checkbox('Send scene narration to HeyGen and use provider credits when I render or audition. This avatar is fictional or authorized.')
        if st.button('Use HeyGen scientist for this project', disabled=not cloud_key_ready or not cloud_permission):
            p['avatar'] = {'provider':'heygen', 'avatar_id':cloud_id.strip(), 'voice_id':cloud_voice.strip(),
                           'locale':cloud_locale.strip(), 'motion_prompt':cloud_motion, 'cloud_authorized':True}
            p.pop('presenter', None)
            for row in rows:
                row['layout'] = 'Presenter side-by-side'
            reset_approvals()
            save('HeyGen scientist selected; scene approvals reset')
            st.success('Cloud scientist selected. Review scenes, then render from Export center.')
        st.caption('The supplied IDs belong to the scientist and voice created in the connected workspace. Your API key must have access to them; enter accessible IDs if using another workspace. Narration must already be in the intended language.')
    from sop_studio.avatar import readiness
    st.subheader('A presenter driven by your narration')
    st.caption('Optional SadTalker portrait animation. Generates face/head movement from speech; hands, body and clothing remain static. This does not reproduce the reference video’s full-body performance. Initial face model: 256 pixels.')
    state = readiness()
    if not state['files_present']:
        st.warning('Presenter engine setup is incomplete. Preview and AI export remain disabled until runtime verification and model downloads finish.')
        with st.expander('Missing setup files'):
            st.write(state['missing'])
        st.caption('Use INSTALL_AI_PRESENTER.bat for explicit setup. Downloads require several GB; core app dependencies stay separate.')
    elif not state['verification']:
        st.info('Engine files are present. No measured presenter benchmark has been saved yet; generate and inspect a short preview first.')
    if state['verification']:
        measured = state['verification']
        if measured.get('output_duration_seconds'):
            st.warning(f'Measured CPU test: {measured["seconds_elapsed"]:.0f} seconds to create {measured["output_duration_seconds"]:.2f} seconds of video. This CPU configuration is impractical for long SOP videos; GPU acceleration is not benchmarked.')
        with st.expander('Measured presenter test'):
            st.json(state['verification'])
    source_type = st.radio('Presenter source', ['Fictional example portrait', 'My authorized photo'])
    portrait = None
    if source_type == 'Fictional example portrait':
        presets = {'Lab scientist': 'fictional_lab_scientist.png',
                   'Lab technician': 'fictional_lab_technician.png',
                   'Original educator': 'fictional_educator.png'}
        current = Path(p.get('avatar', {}).get('portrait', '')).name
        labels = list(presets)
        initial = next((i for i, label in enumerate(labels) if presets[label] == current), 0)
        character = st.selectbox('Fictional character', labels, index=initial)
        selected_portrait = ROOT/'approved_media'/'presenters'/presets[character]
        if selected_portrait.is_file():
            portrait = str(selected_portrait)
        else:
            st.error('The selected fictional portrait is missing from the installation.')
        st.caption('Select a character, then use “Use AI presenter for this project” to save it. Clothing is a presenter costume; follow your SOP for required protective equipment.')
    if source_type == 'My authorized photo':
        photo = st.file_uploader('Portrait photo: clear face, front-facing, relaxed closed mouth', type=['png','jpg','jpeg'], key=f'avatar_photo_{g}')
        if photo:
            portrait = upload_media(photo, 'portrait')
    if portrait:
        st.image(portrait, width=280)
    permission = st.checkbox('This is fictional or I have permission to animate this person’s likeness.')
    device = st.selectbox('Inference device', ['auto', 'cpu'], format_func=lambda x:'GPU when available; retry on CPU after GPU out-of-memory' if x=='auto' else 'CPU only (may be slow)')
    expression = st.slider('Facial expression scale', .5, 1.5, 1.0, .1)
    pose = st.slider('Model pose style', 0, 45, 0)
    preview_text = st.text_area('Short presenter audition', 'Welcome to SOP training.')
    preview_active = jobs.status(Path(p['avatar_preview_job'])) if p.get('avatar_preview_job') else None
    preview_busy = bool(preview_active and preview_active['state'] in ('queued','running'))
    if st.button('Generate actual speaking preview', type='primary', disabled=preview_busy or not state['files_present'] or not portrait or not permission or not settings.get('voice')):
        if not preview_text.strip() or len(preview_text.split()) > 40:
            st.error('Use 1–40 words for an initial performance test.')
        else:
            p['avatar_preview_job'] = str(jobs.start({'task':'avatar_preview', 'portrait':portrait, 'text':preview_text,
                'engine':settings['engine'], 'voice':settings['voice'], 'rate':settings['rate'], 'pronunciation':settings.get('pronunciation',{}),
                'device':device, 'expression_scale':expression, 'pose_style':pose}))
            save('Audio-driven presenter audition started')
            st.rerun()
    if not settings.get('voice'):
        st.caption('Discover and save a voice in Voice studio before generating a speaking preview. The selected voice does not translate narration.')
    @st.fragment(run_every=3)
    def avatar_status():
        project = st.session_state.project
        if not project.get('avatar_preview_job'):
            return
        folder = Path(project['avatar_preview_job'])
        progress = jobs.status(folder)
        st.write('Presenter preview: ' + progress['state'])
        if progress['state'] in ('queued','running'):
            if st.button('Cancel presenter preview'):
                jobs.cancel(folder)
        elif progress['state']=='complete':
            st.video(progress['video'])
            st.json(progress['generation'])
            st.caption('Inspect lips, eyes, teeth, identity consistency and speech alignment. A successful render alone does not establish naturalness or synchronization quality.')
        else:
            st.error(progress.get('error','Preview interrupted.'))
    avatar_status()
    apply_layout = st.checkbox('Apply circular picture-in-picture to existing scenes', value=True)
    if st.button('Use AI presenter for this project', disabled=not state['files_present'] or not permission or not portrait):
        p['avatar'] = {'portrait':portrait, 'portrait_sha256':file_hash(portrait), 'device':device, 'expression_scale':expression, 'pose_style':pose}
        p.pop('presenter', None)
        if apply_layout:
            for scene in rows:
                scene['layout'] = 'Presenter circular picture-in-picture'
        reset_approvals()
        save('AI presenter configuration changed; scene approvals reset')
        st.success('AI presenter selected. Choose a presenter composition in each scene, then re-review and render.')
    if p.get('avatar') and st.button('Disable AI presenter'):
        p.pop('avatar', None)
        reset_approvals()
        save('AI presenter disabled')
        st.rerun()

elif page == 'AI providers':
    import os
    st.subheader('Connect your video services')
    st.caption('Use developer API keys, not account passwords. Presenter services supply their own synchronized speech; Kling supplies contextual clips. Select a provider explicitly before generating. No automatic paid failover is performed.')
    if st.session_state.get('provider_key_notice'):
        st.warning(st.session_state.provider_key_notice)
    for name, label in [('HEYGEN_API_KEY','HeyGen API key'), ('SYNTHESIA_API_KEY','Synthesia API key (Legacy v2 scope)'), ('KLING_API_KEY','Kling developer API key')]:
        session_key = credentials.SESSION_NAMES[name]
        value = st.text_input(label, value=st.session_state.get(session_key,''), type='password', key='provider_'+session_key)
        st.session_state[session_key] = value
        st.caption(('Available' if value.strip() or os.environ.get(name,'').strip() else 'Not configured')+' · '+name)
    st.caption('Keys remain in this app session unless you explicitly save them below. Windows encrypted storage can be unlocked by this Windows account; project downloads and release packages exclude it.')
    if st.button('Save keys encrypted for my Windows account', disabled=os.name!='nt'):
        try:
            values = credentials.environment(st.session_state)
            if not values:
                raise ValueError('Enter at least one API key before saving.')
            credentials.save(ROOT, values)
            st.success('Saved using current-user Windows encryption. Keys load automatically in future sessions.')
        except (RuntimeError, ValueError, OSError) as exc:
            st.error(str(exc))
    if st.button('Forget saved and session keys'):
        (ROOT/'.local'/'credentials.dpapi').unlink(missing_ok=True)
        for key in list(credentials.SESSION_NAMES.values()):
            st.session_state.pop(key,None)
            st.session_state.pop('provider_'+key,None)
        st.session_state.pop('heygen_key_input',None)
        st.rerun()
    st.caption('Environment-provided keys remain configured until removed from the process environment.')
    if st.button('Check Synthesia API access (no generation)'):
        try:
            synthesia.api('videos', key=st.session_state.get('synthesia_api_key','').strip() or None)
            st.success('Synthesia accepted the read request. Avatar access and generation credits still depend on your account.')
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    if st.button('Check Kling API access (no generation)'):
        try:
            kling.api('videos/text2video?pageNum=1&pageSize=1', key=st.session_state.get('kling_api_key','').strip() or None)
            st.success('Kling accepted the read request. Model access and generation credits still depend on your account.')
        except (RuntimeError, ValueError) as exc:
            st.error(str(exc))
    st.divider()
    st.subheader('Use a Synthesia presenter')
    st.caption('Enter an avatar ID available to your Synthesia API account. This does not transfer or recreate the fictional HeyGen scientist. Only select a fictional or authorized Synthesia avatar. Speech uses the avatar’s default voice; language selection here does not translate the script.')
    synth_config = p.get('avatar',{}) if p.get('avatar',{}).get('provider')=='synthesia' else {}
    synth_avatar = st.text_input('Synthesia avatar ID', synth_config.get('avatar_id',''))
    synth_test = st.checkbox('Synthesia test mode (watermarked)', value=synth_config.get('test_mode',True))
    synth_permission = st.checkbox('This Synthesia avatar is fictional or authorized. Send scene narration to Synthesia when I render; production mode can consume credits.')
    synth_ready = bool(st.session_state.get('synthesia_api_key','').strip() or synthesia.configured())
    if st.button('Use Synthesia for presenter scenes', disabled=not synth_ready or not synth_avatar.strip() or not synth_permission):
        p['avatar'] = {'provider':'synthesia', 'avatar_id':synth_avatar.strip(), 'test_mode':synth_test, 'cloud_authorized':True}
        p.pop('presenter',None)
        for row in rows:
            row['layout'] = 'Presenter side-by-side'
        reset_approvals()
        save('Synthesia presenter selected; scene approvals reset')
        st.success('Synthesia selected. Review scenes, then render in Export center. Use Visual generation → Kling AI for contextual clips.')

elif page == 'Voice studio':
    st.subheader('A consistent voice, scene by scene')
    from sop_studio.voice_clone_workspace import controls as voice_clone_controls
    voice_clone_controls(p, ROOT, save)
    if p.get('avatar', {}).get('native_voice_clone'):
        st.info('Your HeyGen presenter uses the authorized cloned voice. The controls below select a separate local/Edge voice for draft auditions; they do not replace the presenter’s cloned speech.')
    engine = st.selectbox('Speech engine', ['Windows offline', 'Edge (online)'], index=0 if settings.get('engine') == 'Windows offline' else 1)
    st.caption('Windows uses installed voices only. Edge sends narration to an online service; availability is not guaranteed. No translation or voice cloning is performed.')
    if st.button('Discover available voices'):
        try:
            if engine == 'Windows offline':
                st.session_state.voice_choices = [{'id':v['id'], 'name':v['name'], 'language': ', '.join(v['languages'])} for v in installed_voices()]
            else:
                with st.spinner('Checking online voice availability…'):
                    st.session_state.voice_choices = [{'id':v['ShortName'], 'name':v['FriendlyName'], 'language':v['Locale']} for v in asyncio.run(edge_voices()) if v['Locale'] in ('en-IN', 'en-US', 'hi-IN', 'or-IN')]
            st.session_state.voice_choice_engine = engine
        except Exception as exc:
            st.error(f'Voice discovery failed: {exc}')
    choices = st.session_state.get('voice_choices', []) if st.session_state.get('voice_choice_engine') == engine else []
    if choices:
        selected = st.selectbox('Available voice', range(len(choices)), format_func=lambda i:choices[i]['name'])
        rate = st.slider('Speech rate', 100, 220, int(settings.get('rate', 155)) if isinstance(settings.get('rate'), int) else 155) if engine == 'Windows offline' else st.select_slider('Speech speed', ['-20%', '-10%', '+0%', '+10%', '+20%'], value='+0%')
        dictionary_text = st.text_area('Pronunciation dictionary (JSON)', json.dumps(settings.get('pronunciation', {}), indent=2), help='Example: {"GMP": "G M P"}. Substitution changes speech and is recorded in the manifest.')
        if st.button('Save voice settings', type='primary'):
            try:
                dictionary = json.loads(dictionary_text)
                if not isinstance(dictionary, dict) or not all(isinstance(k, str) and k and isinstance(v, str) for k,v in dictionary.items()):
                    raise ValueError('Use a JSON object mapping terms to spoken text.')
                settings.update(engine=engine, voice=choices[selected]['id'], language=choices[selected]['language'], rate=rate, pronunciation=dictionary)
                for row in rows:
                    row['language'] = choices[selected]['language']
                    invalidate(row)
                save('Voice and pronunciation changed; scene approvals reset')
                st.success('Voice saved. Re-review the narration for the selected language.')
            except ValueError as exc:
                st.error(str(exc))
    elif not settings.get('voice'):
        st.info('Discover and save an available voice before rendering.')
    if settings.get('voice'):
        st.caption('Saved voice: ' + settings['voice'])
    if rows and settings.get('voice'):
        scene = st.selectbox('Scene to audition / regenerate', range(len(rows)), format_func=lambda i:f'Scene {i+1}: {rows[i]["narration"][:70]}')
        if st.button('Generate scene narration'):
            try:
                with st.spinner('Generating this scene only; unchanged narration is cached…'):
                    audio = generate_cached(rows[scene]['narration'], ROOT, settings['engine'], settings['voice'], settings['rate'], settings.get('pronunciation'))
                st.audio(str(audio))
            except Exception as exc:
                st.error(str(exc))

elif page == 'Timeline':
    st.subheader('Correct the timing at its source')
    st.caption('Adjust clip in-points here. Open Storyboard & script for phrase captions, timed visual switching and scene preview. Phrase times are manually reviewed against audio; no forced alignment is claimed.')
    if rows:
        data = [{'scene':i+1, 'reference':r['reference'], 'topic':r['visual'], 'estimated_seconds':r['seconds'], 'media_offset':r.get('media_offset', 0)} for i,r in enumerate(rows)]
        edited = st.data_editor(data, disabled=['scene', 'reference', 'topic', 'estimated_seconds'], hide_index=True, width='stretch', column_config={'media_offset': st.column_config.NumberColumn('Clip in-point (s)', min_value=0, step=0.1)})
        if st.button('Apply clip in-points'):
            for row, entry in zip(rows, edited):
                if entry['media_offset'] != row.get('media_offset', 0):
                    row['media_offset'] = float(entry['media_offset'])
                    invalidate(row)
            save('Timeline in-points changed')
            st.rerun()
    else:
        st.info('Build scenes to edit their media timing.')
    if p.get('last_files'):
        manifest = Path(p['last_files'][2])
        if manifest.exists():
            timeline = json.loads(manifest.read_text(encoding='utf-8'))['timeline']
            st.dataframe([{'scene':r['scene'], 'start':r['start'], 'end':r['end'], 'start_frame':r['start_frame'], 'end_frame':r['end_frame'], 'alignment':r['alignment']} for r in timeline], hide_index=True)

elif page == 'QA review':
    st.subheader('Review the procedure, not just the presentation')
    reviewer = st.text_input('Reviewer name', key='reviewer')
    if rows:
        current_source = hashlib.sha256(p['source_text'].encode('utf-8')).hexdigest()
        planned_source = p['metadata'].get('storyboard_source_hash')
        source_changed = bool(planned_source and current_source != planned_source)
        if source_changed:
            st.error('Source text changed after planning. Rebuild the storyboard before approval.')
        selected = st.selectbox('Scene to review', range(len(rows)), format_func=lambda i:f'{"✓" if is_approved(rows[i]) else "○"} {i+1:02} · {rows[i]["reference"]}')
        row = rows[selected]
        source_missing = not p['source_text'].strip() or row['original_instruction'] not in p['source_text']
        review_asset = scene_asset(p, row)
        asset_stale = bool(review_asset and not asset_current(review_asset, row, p))
        try:
            validate_cues(row.get('phrase_cues', []))
            asset_stale = asset_stale or any(c.get('asset') and not asset_current(c['asset'], row, p) for c in row.get('phrase_cues', []))
        except ValueError:
            asset_stale = True
        if asset_stale:
            st.error('Attached visual is outdated or changed. Regenerate or reattach a revision-matched asset before approval.')
        if source_missing:
            st.error('This original instruction cannot be traced to the current source text. Import the matching source or rebuild scenes.')
        a, b = st.columns(2)
        a.markdown('**Original source instruction**')
        a.write(row['original_instruction'])
        b.markdown('**Current narration**')
        b.write(row['narration'])
        st.write('Source reference: ' + row['reference'])
        if row.get('phrase_cues'):
            st.markdown('**Phrase timing to verify against audio**')
            st.dataframe([{'start': c['start'], 'end': c['end'], 'caption': c['text'],
                           'visual': (c.get('asset') or {}).get('description', 'Scene visual')} for c in row['phrase_cues']], hide_index=True)
        record = scene_asset(p, row)
        st.write('Demonstration: ' + (record['description'] or record['asset_id'] if record else 'MISSING — labeled placeholder in draft export'))
        for flag in row['flags'] + contradiction_flags(row['original_instruction'], row['narration']):
            st.warning(flag)
        comments = st.text_area('Review decision / comments', row.get('review_comments', ''), key=f'qa_{g}_{selected}')
        confirmed = st.checkbox('I checked wording, sequence, source reference, safety content and the attached visual.', key=f'confirm_{g}_{selected}')
        if st.button('Approve current scene', type='primary', disabled=not reviewer.strip() or not confirmed or source_changed or source_missing or asset_stale):
            try:
                row['generation'] = record.get('generation') if record else None
                row['asset_review'] = {k:record.get(k) for k in ('asset_id', 'status', 'reviewer', 'review_notes', 'sha256')} if record else None
                row['media_sha256'] = file_hash(record['path']) if record else ''
                row['media'] = record['path'] if record else ''
                row['source_text_sha256'] = current_source
                row['presenter_sha256'] = file_hash(p['presenter']) if p.get('presenter') else ''
                approve(row, reviewer, comments)
                save(f'Scene {selected+1} reviewed by {reviewer}')
                st.success('Approval recorded for the current scene content and media checksum.')
            except Exception as exc:
                st.error(str(exc))
        st.caption('Local reviewer names and history are editable files. They are not electronic signatures or a tamper-proof regulated audit trail.')
    else:
        st.info('Create scenes before reviewing.')
    if p['history']:
        with st.expander('Saved change history'):
            st.json(p['history'])

elif page == 'Export center':
    st.subheader('Render, inspect, then distribute')
    with st.expander('Branding, captions and transitions', expanded=True):
        production = settings.setdefault('production', {})
        production['brand'] = st.text_input('Organization / brand', production.get('brand', ''), max_chars=80)
        production['accent'] = st.color_picker('Brand accent', production.get('accent', '#246b50'))
        production['burn_captions'] = st.checkbox('Burn captions into video', value=production.get('burn_captions', False))
        styles = ['Classic', 'High contrast']
        production['caption_style'] = st.selectbox('Caption style', styles, index=styles.index(production.get('caption_style', 'Classic')))
        transitions = ['Cut', 'Fade']
        production['transition'] = st.selectbox('Scene transition', transitions, index=transitions.index(production.get('transition', 'Cut')))
        st.caption('Fade preserves narration timing. Phrase cues control caption changes; scenes without cues use a scene caption.')
    preset = st.selectbox('Output format', list(PRESETS), index=list(PRESETS).index(settings.get('preset', '720p landscape')))
    strict = st.checkbox('Require reviewed demonstrations for every scene', value=True)
    settings['require_complete_source'] = st.checkbox('Require all source segments in the storyboard', value=settings.get('require_complete_source', False), help='Enable for complete SOP training. Disable only when intentionally producing an overview. Source coverage is checked against retained original instructions; narration still needs review.')
    issues = readiness(p, is_approved, strict)
    st.markdown('**Export readiness**')
    if not issues:
        st.success('All source, voice, scene approval and visual checks passed.')
    for issue_index, (target, scene_index, message) in enumerate(issues):
        a, b = st.columns([5, 1])
        a.write('○ ' + message)
        destination = 'Storyboard & script' if scene_index is not None else target
        b.button('Fix →', key=f'fix_{issue_index}', on_click=navigate, args=(destination, scene_index))
    st.caption('30 fps · CPU rendering · source-reference overlays · normalized audio · MP4, SRT, VTT, script, storyboard and checksum manifest')
    reviewed = sum(is_approved(r) for r in rows)
    st.progress(reviewed / len(rows) if rows else 0, text=f'{reviewed} / {len(rows)} scene approvals current')
    assets_ready = all((record := scene_asset(p, r)) and record['status'] == 'approved' and asset_current(record, r, p) for r in rows)
    if strict and not assets_ready:
        st.warning('Attach reviewed, revision-matched media for every scene, or disable the strict check to render a draft with placeholders.')
    if not settings.get('voice') and p.get('avatar', {}).get('provider') not in ('heygen','synthesia','imported-cloud'):
        st.info('Select an available narration voice in Voice studio.')
    active = jobs.status(Path(p['active_job'])) if p.get('active_job') else None
    busy = active and active['state'] in ('queued', 'running')
    voice_ready = bool(settings.get('voice') or p.get('avatar', {}).get('provider') in ('heygen','synthesia','imported-cloud'))
    if st.button('Render training video →', type='primary', disabled=bool(busy) or bool(issues) or not rows or reviewed != len(rows) or not voice_ready or (strict and not assets_ready)):
        try:
            settings['preset'] = preset
            source_hash = hashlib.sha256(p['source_text'].encode('utf-8')).hexdigest()
            if p['metadata'].get('storyboard_source_hash') and p['metadata']['storyboard_source_hash'] != source_hash:
                raise ValueError('Source changed after storyboard planning. Rebuild scenes first.')
            for row in rows:
                record = scene_asset(p, row)
                row['media'] = bound_scene_media(row)
                row['generation'] = record.get('generation') if record else None
                row['asset_review'] = {k:record.get(k) for k in ('asset_id', 'status', 'reviewer', 'review_notes', 'sha256')} if record else None
                # Binding the reviewed asset path does not change content approval; verify checksum first.
                if row.get('media_sha256') and file_hash(row['media']) != row['media_sha256']:
                    raise ValueError('Attached media changed after review.')
                row['review_hash'] = scene_fingerprint(row)
            request = {'rows':rows, 'title':p['title'], 'engine':settings['engine'], 'voice':settings['voice'], 'rate':settings['rate'],
                       'presenter_path':p.get('presenter'), 'media_map':{}, 'preset':preset, 'fps':30,
                       'metadata':{**p['metadata'], 'sop_id':p['sop_id'], 'project_id':p['project_id'], 'current_source_text_sha256':source_hash, 'assets':p['assets'], 'scene_assets':p.get('scene_assets', {}), 'history':p['history']},
                       'strict_media':strict, 'pronunciation_map':settings.get('pronunciation', {}), 'avatar':p.get('avatar'), 'production': production}
            key_name = {'heygen':'HEYGEN_API_KEY','synthesia':'SYNTHESIA_API_KEY'}.get(p.get('avatar',{}).get('provider'))
            cloud_environment = credentials.environment(st.session_state, (key_name,))
            p['active_job'] = str(jobs.start(request, environment=cloud_environment))
            save('Background render started')
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    @st.fragment(run_every=2)
    def render_status():
        project = st.session_state.project
        if not project.get('active_job'):
            return
        folder = Path(project['active_job'])
        state = jobs.status(folder)
        st.progress(state.get('progress', 0), text='Render: ' + state['state'])
        if state['state'] in ('queued', 'running'):
            if st.button('Cancel rendering'):
                jobs.cancel(folder)
                st.info('Cancellation requested. Waiting for the current subprocess to stop.')
        elif state['state'] == 'complete':
            project['last_files'] = state['files']
            st.success('Render complete. Review final playback and the manifest before release.')
            video, subtitles, manifest = map(Path, state['files'])
            st.video(str(video))
            package = json.loads(manifest.read_text(encoding='utf-8'))
            for name, info in package['artifacts'].items():
                path = Path(info['path'])
                if path.exists():
                    st.download_button('↓ ' + name, path.read_bytes(), name, key='download_' + name)
            st.download_button('↓ Review manifest', manifest.read_bytes(), manifest.name, 'application/json')
        else:
            st.error(state.get('error', 'Render interrupted. See worker.log in the job directory.'))
    render_status()

elif page == 'Models & diagnostics':
    st.subheader('Know what this machine can do')
    if st.button('Run hardware and dependency diagnostics'):
        st.session_state.diagnostics = diagnose(ROOT)
    if st.session_state.get('diagnostics'):
        st.json(st.session_state.diagnostics)
    st.markdown('**Model installation is explicit. No model weights are bundled or downloaded automatically.**')
    st.markdown('The renderer uses CPU FFmpeg on low-VRAM machines. Optional SadTalker face animation is available through Presenter studio when setup is verified. Body gestures, Blender animation, semantic embeddings and forced alignment remain unfinished. Recorded footage remains available as a fallback.')
    st.markdown('**Local AI:** Install Ollama independently, review a chosen model’s license and storage requirements, then discover installed models in Storyboard & script. The app only connects to loopback and never starts model downloads.')
    research = ROOT / 'docs' / 'MODEL_RESEARCH.md'
    if research.exists():
        with st.expander('Repository and license research'):
            st.markdown(research.read_text(encoding='utf-8'))
    st.caption('Published benchmarks on other GPUs do not establish GTX 1050 performance. No avatar benchmark has been completed.')

try:
    current = st.session_state.project
    if content_digest(current) != st.session_state.get('_saved_digest'):
        save('Autosaved workspace changes')
    st.caption('Saved locally · ' + st.session_state.project.get('saved_at', ''))
except (OSError, ValueError) as exc:
    st.error('Autosave failed. Keep this tab open and retry Save to workspace: ' + str(exc))

st.divider()
st.caption('◈ SOP TRAINER AI / Local production workspace / Content review required before release')
