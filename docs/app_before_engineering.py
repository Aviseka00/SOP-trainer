"""SOP Trainer Studio: a local production workspace."""
import hashlib
import html
import json
import uuid
from pathlib import Path

import streamlit as st
from engine import ROOT, CATEGORIES, LAYOUTS, extract, storyboard, render

st.set_page_config(page_title='SOP Studio | Production workspace', page_icon='◈', layout='wide')
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;600;700;800&display=swap');
:root{--ink:#172c2a;--muted:#768580;--green:#246b50}
.stApp{background:#f6f7f3;color:var(--ink);font-family:'DM Sans',sans-serif}
h1,h2,h3{font-family:Manrope,sans-serif!important;letter-spacing:-.045em!important;color:var(--ink)}
.block-container{padding-top:2.6rem;max-width:1500px;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#eaf0e8;border-right:1px solid #dbe2d8}
[data-testid="stSidebar"] .block-container{padding-top:2rem}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:#246b50;border-color:#246b50;border-radius:9px}
.stButton>button,.stDownloadButton>button{border-radius:9px;font-weight:600}
[data-testid="stMetric"]{background:white;border:1px solid #e0e6dd;border-radius:14px;padding:18px 22px}
[data-testid="stMetricLabel"]{color:#768580;font-size:12px;text-transform:uppercase;letter-spacing:.07em}
[data-testid="stMetricValue"]{font-family:Manrope,sans-serif;font-weight:700;font-size:30px}
.stTabs [data-baseweb="tab-list"]{gap:24px;border-bottom:1px solid #dce3d9}
.stTabs [aria-selected="true"]{color:#246b50!important}
.stTabs [data-baseweb="tab-highlight"]{background:#246b50}
.brand{font-family:Manrope;font-size:25px;font-weight:800;letter-spacing:-1px;margin-bottom:5px}
.eyebrow{font-size:11px;color:#6c8475;text-transform:uppercase;letter-spacing:2px;font-weight:700}
.hero{background:#e6edde;border:1px solid #d6e1cd;border-radius:18px;padding:30px 34px;margin:20px 0 26px;position:relative}
.hero h2{font-size:32px;margin:8px 0 10px;padding:0;max-width:640px}
.hero p{color:#5a7062;max-width:630px;line-height:1.6;margin:0}
.tag{display:inline-block;background:#f8fbf4;border:1px solid #d6e1cd;border-radius:20px;padding:5px 12px;font-size:11px;color:#43664a;margin-bottom:7px}
.preview{background:#142e2a;border-radius:16px;min-height:285px;padding:32px;color:white;margin-bottom:18px;box-shadow:0 12px 30px #19382b12}
.preview h3{color:#edf5dc!important;font-size:28px;margin:26px 0 18px}
.preview p{color:#c5d4c9;font-size:16px;line-height:1.7}
.preview small{color:#a5c591;letter-spacing:2px;text-transform:uppercase}
.note{color:#7a867c;font-size:12px;line-height:1.6}
</style>''', unsafe_allow_html=True)

DEFAULTS = {'rows': [], 'assets': {}, 'source_text': '', 'training_title': 'Personnel hygiene essentials', 'sop_id': '', 'revision': 0}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def replace_project(data):
    rows = data.get('scenes', [])
    if not isinstance(rows, list) or len(rows) > 80:
        raise ValueError('A project must contain a list of up to 80 scenes.')
    clean = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('narration'), str):
            raise ValueError('Every scene needs narration text.')
        clean.append({'narration': row['narration'], 'visual': row.get('visual') if row.get('visual') in list(CATEGORIES) + ['General'] else 'General', 'layout': row.get('layout') if row.get('layout') in LAYOUTS else LAYOUTS[0], 'reference': str(row.get('reference', '')), 'approved': False, 'media': '', 'seconds': 0})
    st.session_state.rows = clean
    st.session_state.training_title = str(data.get('title', 'Untitled training'))
    st.session_state.sop_id = str(data.get('sop_id', ''))
    st.session_state.source_text = str(data.get('source_text', ''))
    st.session_state.revision += 1
    st.session_state.pop('last_files', None)


def remove_asset(topic):
    st.session_state.assets.pop(topic, None)
    st.session_state.pop(f'media_{topic}', None)
    for scene in st.session_state.rows:
        if scene['visual'] == topic:
            scene['approved'] = False
    st.session_state.revision += 1


def save_upload(upload, prefix):
    digest = hashlib.sha256(upload.getvalue()).hexdigest()[:16]
    path = ROOT / 'approved_media' / f'{prefix}_{digest}{Path(upload.name).suffix.lower()}'
    if not path.exists():
        path.write_bytes(upload.getvalue())
    return str(path)


with st.sidebar:
    st.markdown('<div class="brand">◈ SOP Studio<span style="color:#6d8b68">.</span></div>', unsafe_allow_html=True)
    st.caption('TRAINING, THOUGHTFULLY MADE')
    st.divider()
    st.markdown('**Your production workspace**')
    st.caption('Turn approved procedures into clear, consistent training. Everything stays in your local workspace, except online speech synthesis.')
    st.divider()
    st.markdown('**Voice & delivery**')
    speech_engine = st.selectbox('Speech engine', ['Edge (online)', 'Windows offline'])
    voices = {'English India · Neerja': 'en-IN-NeerjaNeural', 'English India · Prabhat': 'en-IN-PrabhatNeural', 'Hindi · Swara': 'hi-IN-SwaraNeural', 'Hindi · Madhur': 'hi-IN-MadhurNeural', 'Odia · Subhasini': 'or-IN-SubhasiniNeural', 'Odia · Sukant': 'or-IN-SukantNeural'}
    voice = voices[st.selectbox('Narration voice', list(voices), disabled=speech_engine != 'Edge (online)')]
    rate = st.select_slider('Delivery speed', ['-20%', '-10%', '+0%', '+10%', '+20%'], value='+0%') if speech_engine == 'Edge (online)' else st.slider('Words per minute', 100, 220, 155)
    st.caption('Voice selection does not translate narration. Use a reviewed translation for each language.')
    st.divider()
    with st.expander('Open a saved project'):
        project = st.file_uploader('Storyboard JSON', type=['json'])
        if st.button('Open project', disabled=project is None):
            try:
                replace_project(json.loads(project.getvalue()))
                st.rerun()
            except (ValueError, TypeError, AttributeError) as exc:
                st.error(f'Could not open project: {exc}')
    st.caption('LOCAL WORKSPACE • 720P EXPORT')

left, right = st.columns([4, 1])
with left:
    st.markdown('<div class="eyebrow">Workspace / Training production</div>', unsafe_allow_html=True)
    st.title('Good procedures. Great training.')
with right:
    st.markdown('<div class="tag">● Local workspace</div>', unsafe_allow_html=True)
    st.download_button('↓ Save project', json.dumps({'title': st.session_state.training_title, 'sop_id': st.session_state.sop_id, 'source_text': st.session_state.source_text, 'scenes': st.session_state.rows}, indent=2, ensure_ascii=False), 'sop-project.json', 'application/json', use_container_width=True)

rows = st.session_state.rows
reviewed = sum(bool(r.get('approved')) for r in rows)
words = sum(len(r['narration'].split()) for r in rows)
metrics = st.columns(4)
for col, label, value in zip(metrics, ['Storyboard scenes', 'Reviewed & ready', 'Estimated narration', 'Demonstration assets'], [f'{len(rows):02}', f'{reviewed:02} / {len(rows):02}', f'{max(1, round(words / 155))} min' if words else '—', f'{len(st.session_state.assets):02}']):
    col.metric(label, value)

st.markdown('<div class="hero"><span class="tag">FROM PROCEDURE TO PRACTICE</span><h2>A little clarity goes a long way.</h2><p>Bring your SOP, shape the story, and pair every step with the right demonstration. Make training your team can follow with confidence.</p></div>', unsafe_allow_html=True)
source_tab, edit_tab, media_tab, export_tab = st.tabs(['01  Source document', '02  Storyboard', '03  Media library', '04  Review & export'])

with source_tab:
    main, aside = st.columns([2, 1], gap='large')
    with main:
        st.subheader('Start with the source')
        st.caption('Paste your procedure or extract text from an approved document.')
        st.text_input('Training title', key='training_title')
        st.text_input('SOP number / revision', placeholder='e.g. SOP-QA-014 · Rev 03', key='sop_id')
        upload = st.file_uploader('Drop your SOP here', type=['pdf', 'docx', 'txt'])
        if st.button('Extract document text', disabled=upload is None):
            try:
                st.session_state.source_text = extract(upload.name, upload.getvalue())
                if not st.session_state.source_text.strip():
                    st.warning('No text found. Scanned documents need OCR before import.')
            except Exception as exc:
                st.error(f'Unable to read this document: {exc}')
        st.text_area('Procedure text', height=260, key='source_text', placeholder='Paste the approved procedure here…')
        if st.button('Create storyboard →', type='primary', disabled=not st.session_state.source_text.strip()):
            st.session_state.rows = storyboard(st.session_state.source_text)
            st.session_state.revision += 1
            st.session_state.pop('last_files', None)
            st.rerun()
        st.caption('Creating a storyboard replaces the current scenes. Save your project first to keep previous work. Up to 80 source segments are imported.')
    with aside:
        st.markdown('### Your path to production')
        st.markdown('**01 · Bring the procedure**\n\nUse the effective SOP and a descriptive training title.\n\n**02 · Shape each scene**\n\nCheck narration, choose the layout, and add a source reference.\n\n**03 · Make it visual**\n\nAttach approved demonstrations and optional presenter footage.\n\n**04 · Review, then export**\n\nApprove every scene before rendering the final video.')
        st.divider()
        if st.button('Try an example SOP', use_container_width=True):
            replace_project({'title': 'Personnel hygiene essentials', 'sop_id': 'DEMO · For exploration only', 'source_text': 'Wash hands with soap and water before entering the production area.\nWear the approved gown and shoe covers before entry.\nCheck equipment calibration status before use.\nRecord completed training in the designated logbook.', 'scenes': []})
            st.session_state.rows = storyboard(st.session_state.source_text)
            st.rerun()
        st.caption('The example is illustrative and requires review before use.')

with edit_tab:
    if not rows:
        st.info('Your storyboard starts here. Import a procedure or try the example in Source document.')
    else:
        editor, preview = st.columns([1.35, 1], gap='large')
        with editor:
            st.subheader('Give every step a scene')
            selected = st.selectbox('Select scene', range(len(rows)), format_func=lambda i: f'{i+1:02} · {rows[i]["visual"]}  {"✓" if rows[i].get("approved") else "· To review"}')
            row = rows[selected]
            key = f'{st.session_state.revision}_{selected}'
            old = (row['narration'], row['visual'], row['layout'], row['reference'])
            narration = st.text_area('Narration', row['narration'], height=180, key=f'n_{key}')
            categories = list(CATEGORIES) + ['General']
            visual = st.selectbox('Visual topic', categories, index=categories.index(row['visual']), key=f'v_{key}')
            layout = st.selectbox('Composition', LAYOUTS, index=LAYOUTS.index(row['layout']), key=f'l_{key}')
            reference = st.text_input('Source reference', row['reference'], key=f'r_{key}')
            changed = old != (narration, visual, layout, reference)
            if changed:
                row['approved'] = False
                st.session_state[f'a_{key}'] = False
            row.update(narration=narration, visual=visual, layout=layout, reference=reference)
            row['approved'] = st.checkbox('I checked this scene against the approved SOP', value=row['approved'], key=f'a_{key}', disabled=not narration.strip())
            if changed:
                st.caption('Scene changed. Review and approve the updated content.')
        with preview:
            st.subheader('Scene preview')
            st.markdown(f'<div class="preview"><small>Scene {selected+1:02} / {len(rows):02} · {html.escape(visual)}</small><h3>{html.escape(st.session_state.training_title)}</h3><p>{html.escape(narration)}</p></div>', unsafe_allow_html=True)
            asset = st.session_state.assets.get(visual)
            if asset and Path(asset).exists():
                if Path(asset).suffix.lower() in ['.png', '.jpg', '.jpeg']:
                    st.image(asset, use_container_width=True)
                else:
                    st.video(asset)
            else:
                st.caption('No demonstration attached. Export will use a labeled placeholder.')
            st.caption('Text preview · Final composition follows the selected layout and attached media.')
            st.markdown(f'**Source:** {reference or "Add a source reference"}')
            st.markdown(f'**Estimated speech:** {max(1, round(len(narration.split()) / 155 * 60))} seconds at standard speed')

with media_tab:
    st.subheader('The right visual for every step')
    st.caption('Media is stored locally. Replacing an asset resets approvals for scenes using that topic.')
    presenter = st.file_uploader('Optional recorded presenter', type=['mp4', 'mov', 'mkv'], key='presenter_upload')
    new_presenter = save_upload(presenter, 'presenter') if presenter else None
    if new_presenter != st.session_state.get('presenter'):
        st.session_state.presenter = new_presenter
        for row in rows:
            row['approved'] = False
        st.session_state.revision += 1
    st.info('Presenter recordings are muted and looped. Generated narration does not lip-sync the presenter.')
    topics = sorted(set(r['visual'] for r in rows)) if rows else list(CATEGORIES)
    columns = st.columns(2)
    for i, topic in enumerate(topics):
        with columns[i % 2]:
            with st.container(border=True):
                st.markdown(f'**{topic}**')
                media = st.file_uploader('Image or demonstration video', type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'mkv', 'webm'], key=f'media_{topic}')
                if media:
                    path = save_upload(media, 'asset')
                    if st.session_state.assets.get(topic) != path:
                        st.session_state.assets[topic] = path
                        for row in rows:
                            if row['visual'] == topic:
                                row['approved'] = False
                        st.session_state.revision += 1
                if topic in st.session_state.assets:
                    st.caption('✓ Demonstration attached')
                    st.button('Remove asset', key=f'remove_{topic}', on_click=remove_asset, args=(topic,))

with export_tab:
    st.subheader('One final check. Then bring it to life.')
    approved = sum(bool(r.get('approved')) and bool(r['narration'].strip()) for r in rows)
    st.progress(approved / len(rows) if rows else 0, text=f'{approved} of {len(rows)} scenes reviewed')
    missing = sum(not st.session_state.assets.get(r['visual']) for r in rows)
    a, b = st.columns(2)
    with a:
        st.markdown('**Production checklist**')
        st.write(f'{"✓" if rows else "○"} Storyboard created')
        st.write(f'{"✓" if rows and approved == len(rows) else "○"} Every narration reviewed')
        st.write(f'{"✓" if rows and not missing else "○"} Demonstrations attached · {missing} placeholders')
        st.caption('Review source accuracy and final playback with a qualified reviewer before distribution. Automated topic classification does not validate procedures.')
    with b:
        st.markdown('**Export package**')
        st.write('1280 × 720 video · MP4 / AAC')
        st.write('Timed subtitles · SRT')
        st.write('Scene references & timing · JSON')
    if st.button('Render training video →', type='primary', disabled=not rows or approved != len(rows)):
        try:
            bar = st.progress(0.0)
            with st.spinner('Creating narration and composing your training video…'):
                files = render(rows, st.session_state.training_title, speech_engine, voice, rate, st.session_state.get('presenter'), st.session_state.assets, progress=bar.progress)
            st.session_state.last_files = [str(p) for p in files]
            st.success('Your export is ready. Review playback before distribution.')
        except Exception as exc:
            st.error(f'Rendering failed: {exc}')
    if st.session_state.get('last_files'):
        video, subtitles, manifest = map(Path, st.session_state.last_files)
        if all(p.exists() for p in (video, subtitles, manifest)):
            st.caption('Most recent render · Changes to your project require a new render.')
            st.video(str(video))
            for col, path, label, mime in zip(st.columns(3), [video, subtitles, manifest], ['↓ Video', '↓ Subtitles', '↓ Review manifest'], ['video/mp4', 'text/plain', 'application/json']):
                col.download_button(label, path.read_bytes(), path.name, mime, use_container_width=True)

st.divider()
st.caption('◈ SOP STUDIO     /     Built for clear procedures and confident teams.     /     Local-first production')
