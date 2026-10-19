# SOP Trainer AI — cloud-tested workflow 0.7.0

The default interface is now **Create training**, with five steps: **Upload SOP → Generate content → Add voice → Design video → Generate training video**. Use the numbered sidebar buttons or Continue/Previous. The design step includes visual generation and scene review; the last step shows blocking items, renders in the background and provides video/caption downloads. Local narration, cloud presenter voice and authorized voice cloning remain available. The full workspace is retained under **Advanced tools**.

For a new Windows PC, see [office PC setup](docs/OFFICE_PC_SETUP.md): clone this repository, run `INSTALL_WINDOWS.bat`, then `START_WINDOWS.bat`. Python 3.11 is recommended. Generated demo videos, private projects, voice recordings, API keys and optional models are excluded from Git; configure services separately on each PC.

## Production workspace improvements

### Clone an authorized voice from video/audio

Open **Voice studio → Clone an authorized voice from video or audio**. Upload MP4, MOV, MKV, WebM, AVI or another listed FFmpeg-supported media format (up to 500 MB), choose a 5–180 second segment and extract a mono WAV locally. Preview it, enter the speaker/authorization reference and confirm permission plus cloud submission. Clear single-speaker recordings of 1–3 minutes work best; extraction does not separate mixed speakers or background music. Silent, missing and too-short audio are rejected.

The app uses the configured HeyGen API key to create an instant clone, check its status and audition cloned speech. API access must allow voice cloning and applicable provider usage charges apply. Once ACTIVE, select a HeyGen presenter in Presenter studio and use **Use cloned voice for AI presenter** in Voice studio. This resets content approvals and presenter playback review. The renderer synthesizes cloned speech, passes that exact audio to HeyGen audio-to-video, then preserves the returned performance's own speech. It does not dub a cloned track over an unrelated mouth performance. Cloned narration is limited to 5,000 characters per scene; split longer scenes.

Voice samples/source uploads stay in `.local/voice_samples` until removed locally. Only the extracted WAV is sent when Create is explicitly clicked. Speaker attestation and sample hashes are retained with the clone and presenter configuration; no API key is saved in project/job records. Uncertain clone or speech submissions are not automatically resubmitted. Live cloning and similarity quality require a real authorized sample and provider validation; automated tests use synthetic tones and mocked provider responses. This integration is for HeyGen cloud presenters; it does not register a Windows or Synthesia voice.

Provider references: [Instant clone](https://developers.heygen.com/docs/voices/heygen-voice-instant-clone), [cloned speech](https://developers.heygen.com/docs/voices/heygen-voice-speech), [audio-driven presenter](https://developers.heygen.com/audio-to-video).

Presenter studio now includes **Apply polished training preset** (1080p composition, high contrast burned captions, fades, full-source storyboard checks), a missing-source-segment report, and an explicitly credit-authorized cloud audition for HeyGen/Synthesia. Auditions preserve original provider speech, reuse the existing generation cache and record playback review bound to presenter configuration and narration. Export center lets you choose complete-source training or an intentional overview. Composition resolution does not increase the detail of a lower-resolution provider clip. Source-segment coverage compares retained instructions and is not proof that an edited narration preserves every requirement.

- Guided eight-step production path with Back/Next controls. Advanced tools remain in the sidebar.
- Workspace changes autosave after interactions. Source forms commit when submitted; unfinished form fields are not saved. Resume the latest saved project from Dashboard. Sidebar → Recover a previous version restores a snapshot while retaining the current version in history.
- Storyboard & script now combines original source, narration editing, reviewed visual selection, audio audition, background scene preview, phrase timing and scene approval. Narration edits save automatically after committing the text field.
- Export center lists blocking issues with Fix links and provides organization branding, accent color, burned captions, Classic/High contrast caption styles and optional short fades. Fades preserve audio duration and scene timing.
- Phrase captions and visual cues use explicit start/end seconds checked against measured narration at render time. Edge auditions with actual word-boundary sidecars can populate phrase cues; Windows offline cues require manual timing. Listen and review before approval. No forced alignment or estimated phoneme precision is claimed.
- Phrase visual choices are limited to reviewed, intact assets matching the SOP revision and scene content. Switching supports demonstration full screen and presenter side-by-side layouts. A gap keeps the base visual. Phrase captions are included in SRT/VTT and optionally burned into video.
- Scene previews are drafts using the local voice and recorded presenter composition. They do not approve the project or trigger paid cloud presenter generation; full cloud performance remains part of export.

Changes to narration, media or cues invalidate scene approval. Re-check pronunciation and timing after changing voice settings. Final playback review remains required.

A Windows Streamlit application for source-traceable SOP storyboards, reviewed local media, real narration and FFmpeg training-video export. This release completes a tested foundation milestone; it does **not** implement the full photorealistic digital-human brief.

New overview path: **Source document → Summary & key points → Visual generation → Presenter studio → QA review → Export center**. See `docs/TRAINING_WORKFLOW.md`. The summary works locally using extractive selection, with optional Ollama rewriting. HeyGen cloud performance requires your API key in Presenter studio and provider credits; the chat connector does not provide app API access.

Open **AI providers** to configure HeyGen, Synthesia or Kling developer API keys. Keys can stay in session memory or be explicitly saved using Windows current-user encryption. Choose Synthesia presenter scenes there, or **Visual generation → Kling AI** for contextual clips. API access is distinct from website login credentials. See `docs/VIDEO_PROVIDERS.md` for supported features and limitations.

The sample SOP has now been tested through actual HeyGen cloud generation and scene-bound import into the app compositor. See `docs/CLOUD_ACCEPTANCE.md`. Native certificate-store support fixes the local Python TLS connection problem without disabling certificate verification. Both saved provider keys passed read-only checks; the Kling generation attempt was rejected and its account-usage API reported no active resource package. Local contextual animations were used explicitly in the finished demonstration.

## Start

1. Install Python 3.10 or newer. Python 3.11 is preferred for a fresh setup; this release was tested on the existing Python 3.10 installation.
2. Run `INSTALL_WINDOWS.bat`. It installs declared dependencies into the project `.venv`, without administrator access, subscriptions or AI-model downloads.
3. Run `START_WINDOWS.bat`. Open the local address displayed, usually http://127.0.0.1:8501.
4. Open Dashboard → hand-hygiene example, or import your own source in Source document.
5. Save source information, build the storyboard, edit/review scenes and attach reviewed media in Presenter & media.
6. Discover actual available voices in Voice studio and save a voice. Windows is offline; Edge is optional and online.
7. Review each scene with a reviewer name in QA review, then render in Export center.
8. Save projects to the local workspace. Previous saved snapshots remain in `projects/<id>/history/`.

Selecting a voice does not translate source text. The bundled fictional SOP is for application exploration only, not a site procedure. Headings and metadata are preserved as draft scenes; remove unwanted spoken scenes explicitly in Storyboard & script.

In **Presenter studio**, choose **Fictional example portrait → Lab scientist or Lab technician**, then click **Use AI presenter for this project**. Both are original fictional portraits generated with the built-in image tool; exact prompts are in `docs/LAB_PRESENTER_PROMPTS.txt`. These new portraits have not yet received separate animation benchmarks.

## Automatic images and animations (0.3.0)

Building a storyboard now starts a background visual-generation job by default. Open **Visual generation** to monitor it and attach completed results, or generate an illustration/animation for one scene or every scene. Choose Automatic to interpret the narration, or select a template yourself.

The built-in generator creates real PNG diagrams and three-second MP4 loops for soap application, hand rubbing, rinsing, drying, PPE, generic fluid-bed airflow/particle movement, equipment, surface wiping, documentation, material transfer and warnings. Prohibited actions always produce a warning illustration. Unknown contexts receive a source process card; unsupported procedural details are not invented. Each scene has its own attachment so different actions within the same topic do not share an incorrect clip.

These are local, deterministic 2D schematics, not diffusion-generated photographs, anatomically exact hand demonstrations, equipment simulations or photorealistic video. No downloads, API or GPU are required. Technical labels are English; they are not translated automatically. Schematics remain visibly labeled, and human review is required. Numerical operating settings, contact times and missing acceptance criteria are never fabricated by the generator.

In Visual generation, preview the result and record technical reviewer + review notes + verification. Then approve the narration in QA review and export normally. Generated assets start as drafts; strict export rejects unreviewed visuals. Editing narration/context marks the old generated visual outdated. Generation supports cancellation, cached reuse and recovery of completed scenes after interruption.

A real narrated demonstration is bundled under `examples/generated_visuals/`. Its diagrams are engineering examples, not approved site training media. The generation uses template/keyword interpretation; arbitrary scenes, multilingual interpretation and realistic 3D procedural motion remain future work.

## Implemented and tested

- TXT, PDF and DOCX extraction; ordered DOCX tables; empty/invalid/scanned-file checks.
- Conservative source-preserving scene planning with section/line references, source metadata, warnings, original instructions and no silent 80-scene truncation.
- Validated project/scene records, atomic saves, version snapshots, source/artifact hashes, reviewer comments and content-bound approval resets.
- Media metadata with topic, SOP/revision applicability, reviewer, source, usage rights and integrity checks. Retrieval is exact metadata matching.
- Actual installed Windows voice selection, cached speech generation, pronunciation substitutions and audio normalization. David and Zira were discovered on the target PC; spoken video testing used David.
- Four recorded-presenter layouts; 720p landscape, 1080p landscape and 1080p portrait; 30 fps; source-reference overlays and measured scene timelines.
- Background render processes, progress, cancellation, bounded subprocesses, job logs and interrupted-worker detection.
- MP4, SRT, VTT, script, storyboard JSON and checksum/review manifest export. MP4 decodability is checked before completion.
- Eleven-page workspace with scene preview, source comparison, clip in-point editing, QA controls and system diagnostics.

## Integrated, but not live-service verified

- Optional loopback-only Ollama explanation generation with structured JSON checking. Narration stays unchanged; explanations remain reviewable. Runtime/model installation is separate.
- Edge online speech, live voice discovery and TTS-supplied word-boundary ingestion. Network service availability and online language output were not verified here. No online English/Hindi/Odia availability is claimed without discovery and a successful audition.


## Optional AI presenter prototype (0.4.0)

**Presenter studio** integrates the real SadTalker CLI in a separate `.avatar_venv`. It uses a fictional sample portrait or an authorized uploaded photo and drives facial/head animation from each scene’s actual speech. An explicit installer, model-download records, short-audition worker, portrait/audio/model cache hashes, expression/pose controls, CPU mode, cancellation and export provenance are included. Circular picture-in-picture is now available alongside the existing compositions.

An actual CPU test produced a 55-frame / 2.2-second speaking clip in 764.72 seconds (about 12 minutes 45 seconds). The complete compositor was tested using that real animation and its original speech audio. This CPU speed is impractical for long SOP videos; GTX 1050 acceleration remains untested. Setup downloads and model inference must succeed on each installation before this optional feature is usable. Presenter studio lists missing files and disables generation while setup is incomplete. File readiness is not a quality certification; use the measured benchmark and inspect actual playback. No reference-video hand gestures, moving body, translation or perfect lip-sync is claimed. The initial face model is 256 pixels and CPU presenter scenes are limited to 10 seconds (30 seconds with a verified CUDA runtime) without silent truncation. See [presenter setup and status](docs/PRESENTER.md).

## Not implemented

Verified phoneme alignment, controlled gaze/blink synthesis, hand/body gestures, digital twins, voice cloning, semantic embedding retrieval, forced alignment, Blender animation, optional AI-generated procedural visuals, a download/rollback model manager, music ducking, intro/outro cards and verified multilingual caption shaping. Recorded presenter footage is muted and looped; its mouth movements do not follow generated narration. Offline SAPI provides scene timing, not word or phoneme alignment.

The default strict export setting requires reviewed demonstrations for all scenes. Turning it off permits a **draft** with clearly labeled placeholders. This is not an approved procedural demonstration. Review final playback before distribution.

## Hardware and performance

Diagnostics detected Intel CPU, 15.9 GB RAM and NVIDIA GTX 1050 with 4096 MB VRAM / driver 531.14 on this PC. The compositor uses bounded CPU/libx264 processing and does not load CUDA models. No avatar benchmark has been performed. Estimated narration duration is a reading-speed estimate; actual render timings use measured audio and frame counts.

No paid APIs, credit cards or mandatory subscriptions are required. Online Edge sends narration off-device. The web server binds to loopback and Streamlit usage telemetry is disabled by project configuration. Source files, project history and media remain local.

## Tests and diagnostics

- `TEST_WINDOWS.bat`: unit tests, real FFmpeg layouts, actual Windows narration, background job lifecycle and Streamlit navigation/edit tests.
- `DIAGNOSE_WINDOWS.bat`: hardware/dependencies and pip consistency.
- `.venv\Scripts\python.exe -m unittest discover -s tests -v`: suite without the opt-in offline speech test.
- Set `SOP_TEST_SPEECH=1` to include actual Windows speech. Run normally outside restricted sandboxes for SAPI and Streamlit tests.
- `scripts/model_setup.py`: optional runtime inspection only; no weight downloads.
- `scripts/package_release.py`: rebuild a portable source ZIP, excluding private projects, caches and environments.

See [test evidence](docs/TEST_RESULTS.md), [engineering audit](docs/AUDIT_AND_PLAN.md), [troubleshooting](docs/TROUBLESHOOTING.md), [official repository research](docs/MODEL_RESEARCH.md) and [exact continuation work](docs/CONTINUATION.md).

## Data and compatibility

`engine.py` keeps the previous `extract`, `storyboard`, `render` and utility imports available. `render` still returns `(mp4, srt, manifest)` and accepts pre-existing narration audio for integration tests. New schema records require current review fingerprints; legacy simple rows retain their approval flag with a manifest label indicating legacy approval. Imported storyboard JSON opens as a new draft with paths detached and approvals reset.

`legacy_pro.py` is preserved but unsupported. The before-refactor source snapshots are in `docs/`. `requirements.txt` pins tested direct dependencies; `requirements-lock.txt` records the full Python 3.10/Windows environment. The ZIP excludes `.venv`, models, private source uploads and ordinary user outputs. The source package requires first-time dependency installation.

## Review limitations

Checksums, comments and snapshots support human review; they are not electronic signatures, regulatory validation or 21 CFR Part 11 compliance. The workspace is designed for a single local operator; concurrent edits, access control, signed/tamper-resistant audit trails and formal release approval require further engineering and validation. Model explanations and heuristic flags cannot certify correctness. A qualified reviewer must verify the effective source, visual demonstrations, pronunciation and final playback.

