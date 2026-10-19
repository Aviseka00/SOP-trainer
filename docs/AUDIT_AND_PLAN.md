# Engineering audit and execution plan

## Starting state

The workspace already contained the extracted ZIP files listed in the brief. No ZIP was present to extract again. All three Python source files, requirements, launcher and README were inspected. `legacy_pro.py` is preserved as a historical standalone application; the supported entry point is `app.py`.

Working design: text/PDF/DOCX ingestion, category heuristics, scene editing, Edge/Windows speech calls, FFmpeg composition, MP4/SRT/JSON export. None of those established avatar synthesis, verified language availability, regulatory validation or target-hardware performance.

Problems found: silent 80-segment truncation, weak schema checks, no persistent workspace history, no source checksums, generic references, DOCX tables moved after all paragraphs, stale review state, hard-coded unverified voice names, synchronous UI rendering, no cancellation, no render preflight, cropped demonstrations, unused filter outputs in full-screen presenter composition, no VTT/script package and no automated tests. The first UI redesign from the prior turn added convenience but did not solve these engine issues.

## Ordered implementation

1. Preserve source and introduce validated scene/project records, warnings, section references and atomic local saves.
2. Bind reviews to content and media checksums; retain source files and prior project snapshots.
3. Replace rendering internals while retaining the original public engine facade; test actual FFmpeg layouts, captions and audio.
4. Run rendering in a worker process with disk-backed status, cancellation, logs and failure recovery.
5. Integrate project, source, script, media, voice, timeline-in-point, QA, export and diagnostics screens.
6. Execute unit, UI and spoken-narration integration tests; deliver source ZIP and Windows setup.
7. Only after this foundation, validate advanced speech alignment, retrieval and digital-human engines individually.

Steps 1–6 are implemented in this release. Phase 2 is partial: cached speech, optional TTS word-boundary ingestion, scene synchronization, clip in-point editing and local Ollama explanation adapters exist. These are not substitutes for forced alignment, semantic retrieval or phrase-level visual timing. The Ollama and online speech integrations require live external services and are not marked end-to-end tested.

## Architecture

- `sop_studio/ingestion.py`: strict input extraction, conservative planning, metadata and heuristic contradiction flags.
- `schema.py`: schema validation, source-preserving records and review fingerprints.
- `storage.py`: atomic JSON saves, saved version snapshots and local project listing.
- `media.py`: asset records, checksum verification and exact topic/SOP/revision retrieval.
- `speech.py`: cached subprocess speech generation, pronunciation mapping, installed voice discovery, online word-boundary ingestion.
- `llm.py`: loopback-only Ollama JSON explanation adapter, exact original narration retained.
- `process.py`, `jobs.py`: bounded subprocess execution, cancellation, background job lifecycle and logs.
- `composition.py`: measured audio, frame-based timing, four layouts, three resolutions, reference overlays, exports and artifact hashes.
- `diagnostics.py`: CPU, RAM, NVIDIA memory/driver, disk and dependency reports.
- `app_workspace.py`, `theme.py`: Streamlit workspace; `app.py` re-executes it on reruns.

## Scope boundaries

No artificial lip-sync or simulated model output has been added. No photorealistic avatar model, voice cloning model, Blender renderer, body motion engine or model downloader has been installed. Source interpretation is conservative heuristics plus optional reviewable explanations, not autonomous procedural validation. Media matching is exact metadata matching, not semantic embeddings. The timeline edits clip in-points; it does not yet schedule multiple phrase-level demonstrations inside a scene. Subtitles are sidecar files; burned-in multilingual captions, music ducking, intro/outro branding and formal release signatures are unfinished.

## 0.3.0 update

Local text-driven 2D illustration and animation templates are implemented in visuals.py and integrated through per-scene media records, background jobs, a tenth workspace page, technical review and export provenance. This supersedes the earlier absence of generated diagrams. Blender, diffusion-generated images, realistic procedure footage and synthetic presenter capabilities remain unfinished.
