# Release test evidence — 17 October 2026

## Environment

Windows build 26300, Intel CPU (8 logical processors), 15.9 GB RAM, NVIDIA GTX 1050 4096 MB VRAM, driver 531.14. Python 3.10.0. Exact installed package versions are in requirements-lock.txt. FFmpeg 7.1 was supplied by imageio-ffmpeg. Rendering used CPU/libx264, not CUDA.

The first attempt to install dependencies in the sandbox failed on DNS access. Installation into the workspace virtual environment succeeded with network access. Windows SAPI and the Streamlit test runner required normal Windows execution outside the restricted sandbox. These restrictions were not reported as missing hardware capabilities. No administrator privileges or model downloads were needed.

## Automated suite

Command: set `SOP_TEST_SPEECH=1`, then run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

**Result: all 20 tests passed, no skips, approximately 20.4 seconds for the release run.**

Coverage:

- Source line preservation beyond 80 segments, section references, revision metadata, equipment IDs and prohibition flags.
- Empty/invalid/unsupported source rejection, real PDF extraction, scanned-PDF rejection and DOCX paragraph/table ordering.
- Scene validation, empty narration, invalid layouts, nonfinite timing values and missing reviewer rejection.
- Approval invalidation after narration changes, atomic project saves, prior-version snapshots and project path traversal rejection.
- Asset applicability by exact SOP/revision and checksum-change rejection.
- Missing FFmpeg, missing demonstrations, mismatched narration counts and unavailable model errors.
- Pronunciation term boundaries and cancellation before/during a real running subprocess.
- Actual background worker success and missing-audio failure with disk-backed status and logs.
- Real FFmpeg output for all four presenter layouts; portrait and landscape 1080p plus 720p output.
- Exact 48-frame / 1.6-second output from a four-scene timing fixture, MP4 decodability and exported artifact SHA-256 verification.
- Actual offline speech synthesis from the fictional sample SOP, narration-to-video rendering and caption/manifest export.
- All nine Streamlit pages through the supported `app.py` entry point, reruns, example creation, narration editing and approval reset.

`python -m compileall` passed. `pip check` reported no broken requirements. Expected Streamlit test-context warnings and an upstream PyMuPDF import deprecation notice do not indicate test failures.

## Real speech artifact

The acceptance workflow reads examples/hand_hygiene.txt, extracts and plans it, selects source sections 3.2/3.3/3.4, records engineering reviews, synthesizes actual Microsoft David narration, normalizes the audio, and renders the three scenes. The resulting video is 1280 × 720 at 30 fps. Its 423 decoded frames (14.1 seconds) match the manifest's 423-frame timeline. It includes SRT, VTT, training script, storyboard and a checksum manifest with original source checksum and references.

This sample has deliberately labeled demonstration placeholders. It proves real source ingestion, speech and composition, not clinical/GMP correctness or approval of real demonstrations. Integration fixtures separately exercise attached image media and all presenter layouts using generated test colors. No real pharmaceutical demonstration asset was supplied by a qualified reviewer.

The generated sample MP4 and sidecars are copied into the release ZIP under examples/acceptance/. Paths inside its manifest describe the original machine; artifact checksums are portable.

## Manual inspection

The running dashboard was checked in a browser. A dark-theme contrast conflict was found and corrected with explicit light-theme configuration. Metric values, sidebar navigation, hero text and controls were then visually verified. A decoded frame from the real acceptance MP4 was inspected; the placeholder notice was moved above the reference overlay to keep it fully readable.

## Not validated

No lip-sync model, natural facial/body animation, avatar sync metric, GPU out-of-memory model test, CUDA compatibility benchmark, embedding retrieval accuracy test, Blender animation test, forced-alignment measurement, online Edge language output or live Ollama inference benchmark was performed. Those capabilities are not delivered as complete. No regulatory validation or Part 11 compliance testing was performed. The Windows installer dependency path was executed through equivalent commands; the full interactive first-install batch flow on a clean Python 3.11 machine remains unverified.

## 0.3.0 contextual visual generation

The expanded suite contains **28 tests**, all passing in the final 29.6-second run, including all previous foundation tests. It verifies automatic text-to-template selection, distinct actions within the same topic, safety/prohibition overrides, real pixels from all 13 schematic templates, animated frame changes, generated-file caching, source-change invalidation, draft-only initial asset status, technical approval requirements, background generation of distinct scene assets, strict-export rejection of draft visuals, actual animated-media composition and manifest provenance. A dedicated acceptance test confirms storyboard creation automatically launches animation generation and attaches the correct soap illustration to the scene. Streamlit tests cover all ten pages plus generation, automatic result attachment and the technical-review form.

The real narrated sample in `examples/generated_visuals/` uses locally generated soap, rubbing, rinsing and fluid-bed schematics combined with actual Windows speech. Its generated assets remain marked as engineering examples, not approved site training. This release adds local deterministic 2D graphics only; no diffusion model, photorealistic action video, anatomically verified motion or 3D simulator was installed.

A Windows transient file-sharing race was observed during concurrent status polling. Bounded retries were added to both atomic replacement and JSON status reads, and subsequent full-suite runs passed. Final composition reserves space below the image for reference overlays, keeping source captions and schematic disclaimers visible. Static soap and fluid-bed frames and the generated video were visually inspected.


## 0.4.0 real presenter acceptance — 18 October 2026

The optional SadTalker environment passed import verification and pip consistency checks. Its first complete CPU inference produced a real, decodable talking-face video: 55 frames at 25 fps (2.2 seconds), with 764.72 seconds wall time. The fictional portrait and actual Microsoft David narration were used. Five sampled frames show changing mouth shapes; this is not a phoneme-level accuracy certification. Body and clothing stay static. GTX 1050/CUDA acceleration was not tested.

A separate end-to-end compositor acceptance run reused the real generated animation with the original cached speech and circular picture-in-picture. The resulting manifest identifies SadTalker provenance and the exact generated-video hash. The automated optional acceptance test verifies that the final decoded frame count matches its manifest. Regression coverage now includes the Presenter studio page, missing-engine errors and invalid-control rejection. Use SOP_TEST_AVATAR=1 only after completing the real benchmark and populating its cache. Without it, that acceptance test is intentionally skipped.

The initial runner’s upstream module path error was corrected before the successful measured inference. The CUDA download was cancelled in favor of the smaller CPU compatibility test; no GPU performance result is claimed. CPU speed is impractical for long SOP videos.

Final 0.4.0 release run: **31 tests passed, no skips, in 41.59 seconds**, with both SOP_TEST_SPEECH=1 and SOP_TEST_AVATAR=1. Both isolated and core pip consistency checks passed.
