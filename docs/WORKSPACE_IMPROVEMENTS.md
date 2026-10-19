# Workspace improvements — 19 October 2026

Implemented guided navigation, interaction-based autosave, recent-project recovery, snapshot restore, unified scene editing/review, background draft scene previews, actionable export checks, organization branding, caption styles, optional fade transitions and phrase caption/visual cues.

Validation: `SOP_TEST_SPEECH=1 .venv/Scripts/python.exe -m unittest discover -s tests -v` (set the environment variable using the host shell).

58 tests ran successfully; one optional cached avatar benchmark test was skipped because its fixture was unavailable. Included real Windows speech synthesis, actual FFmpeg renders, Streamlit page navigation and edits, disk-backed autosave, snapshot restoration, invalid timing rejection and frame-color verification before/during/after a visual cue. The phrase render fixture also verifies SRT times and the unchanged 60-frame video duration with branding, burned captions and fades enabled. Local server health returned HTTP 200.

Phrase timing uses manual audio-reviewed seconds, or actual Edge word boundaries when present in an audition sidecar. No automatic forced alignment is implemented. Audio-duration checks happen during rendering. Phrase visual switching supports demonstration full screen and presenter side-by-side; captions support every layout. Draft scene preview uses a saved local voice and recorded presenter; it does not submit cloud generation. Source forms save on submission; narration fields commit on blur or their normal Streamlit commit gesture. Final playback and technical review remain necessary.

Autosave is for one local operator. Existing snapshots and editable reviewer records do not provide regulated electronic signatures or multi-user conflict resolution.
