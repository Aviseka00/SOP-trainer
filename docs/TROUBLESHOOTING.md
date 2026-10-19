# Windows troubleshooting

**First launch:** run `INSTALL_WINDOWS.bat`, then `START_WINDOWS.bat`. A standard Windows user account is sufficient. Python 3.10+ is supported; 3.11 is preferred when installed. The launcher binds to 127.0.0.1 so the application is local to this computer.

**Package download fails:** verify network/DNS/proxy access to PyPI. Re-run the installer. It reuses `.venv` and does not download AI models. `requirements-lock.txt` records the exact full dependency set tested on Python 3.10/Windows; a fresh platform may need its own lock.

**Missing FFmpeg:** run the installer; `imageio-ffmpeg` supplies an executable. `DIAGNOSE_WINDOWS.bat` reports the selected binary. Distribution licenses for FFmpeg and included codecs must be considered before redistributing an environment; the ZIP contains source, not a copied FFmpeg binary.

**Offline voice discovery fails:** verify Windows Speech voices are installed. Run outside restricted sandboxes; the engineering sandbox blocks SAPI COM access even though normal Windows execution succeeds. The app lists only actual installed voices. Installing a display language does not guarantee a SAPI voice. Hindi/Odia offline synthesis is not asserted.

**Online voice/speech fails:** Edge requires internet and a reachable speech service. Discovery times out; generation is bounded by the speech worker timeout. Switch to a discovered Windows voice or provide a verified translation for a compatible voice. Changing voice never translates text.

**Scanned/encrypted PDF or invalid file:** use an unlocked text-based PDF, DOCX, UTF-8/UTF-16 TXT or paste reviewed text. OCR and PPTX are not installed. Extraction refuses empty, oversized and unreadable input rather than silently substituting source characters.

**Approvals disappear:** content, source, media, presenter or voice changes invalidate review. Rebuild the storyboard if source text changed. Check original instructions and current media checksums before approving again. JSON imports deliberately detach paths and reset approvals.

**Render disabled:** save a discovered voice, review each scene with a reviewer name, and attach reviewed media matching the current SOP number and revision. Disable the strict media check only to make a draft with labeled placeholders. Missing attached files and changed media hashes are errors.

**Render error / cancellation / interrupted process:** inspect `jobs/<job-id>/worker.log` and `status.json`. Cancel through Export center. Subprocesses are polled and killed when cancellation is requested; completed cached speech remains available. Retry starts a new composition and reuses matching speech. Segment-resume and segment caching are not implemented. Interrupted workers are detected when status is read, though PID reuse after a long interval remains a limitation.

**Not enough disk or memory:** choose 720p and short scenes, free workspace disk and close other large applications. Rendering uses bounded CPU threads and no CUDA model allocation. The preflight disk threshold is a basic guard, not an accurate forecast of a long video's required storage. Move the entire project to a drive with space if necessary.

**No digital human:** this release composites recorded footage. Lip-sync, blinking/expression synthesis, gesture generation and GPU avatar benchmarks are unfinished. Do not install incompatible CUDA stacks into the core `.venv`; see MODEL_RESEARCH.md and CONTINUATION.md.

**A saved export opens with old content:** each export is a snapshot. Render again after edits. MP4, SRT and manifests use a unique job ID. Manifest paths refer to the creating computer; checksums and filenames remain useful when moving files.

**Review control limitations:** local files are editable, names are self-reported, and snapshots are not signed or access-controlled. These controls do not constitute regulatory validation or 21 CFR Part 11 compliance.
