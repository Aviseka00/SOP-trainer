# Optional audio-driven presenter

The supplied reference was inspected by sampling frames across its 107.5-second, 1920×1080, 30 fps recording. It shows a standing educator, explanatory screens, gestures, pharmaceutical cutaways and circular picture-in-picture. Frame inspection does not prove whether that person was filmed or synthesized, nor whether the audio is accurately synchronized.

This integration targets a more limited, measurable step: a still portrait plus actual scene narration passed to the official [SadTalker engine](https://github.com/OpenTalker/SadTalker). The upstream engine provides face/head animation. Hands, body and clothing in the portrait stay static. A 256-pixel face model cannot establish the reference's level of image quality or full-body performance.

## Setup and status

Run `INSTALL_AI_PRESENTER.bat` explicitly to install the separate `.avatar_venv`, source under `external/SadTalker`, model weights under its checkpoints/face-analysis folders, and setup records under `models/sadtalker`. Expect several GB of disk space and long first downloads. No global Python or core app dependencies are replaced. CPU is the initial compatibility target; CUDA is not claimed benchmarked until an actual GPU test is recorded.

This isolated dependency set targets **Python 3.10**. The core application can use a newer supported Python independently; install Python 3.10 alongside it for the optional presenter. The installer uses `py -3.10` when available or the core environment only when it is already Python 3.10. It does not attempt to build incompatible old vision libraries under Python 3.11+.

Presenter studio reports missing files and stays disabled until the runtime verification marker and required models exist. `runtime.json` means imports/basic device operation passed; it does not mean animation quality passed. `benchmark.json` is written only after `scripts/benchmark_presenter.py` produces a decodable video driven by actual synthesized speech. Inspect the resulting video separately for lip alignment and facial artifacts.

## Use

1. Discover and save an available narration voice in Voice studio.
2. Open Presenter studio and select the fictional sample or upload an authorized photo.
3. Confirm you have permission for the likeness. Generate a short speaking audition and inspect it.
4. Select Use AI presenter for this project. This invalidates scene approvals.
5. Choose a presenter layout for the scenes that should show it, review again and export.

Each scene's measured narration audio drives its own generated presenter clip. Audio, portrait and model manifest hashes key the cache; the output manifest records provenance and timing. A failed model invocation raises an error rather than substituting a still image or unrelated recording. Auto device mode can retry on CPU after a recognized GPU out-of-memory error; CPU-only use can be slow.

CPU scenes are limited to ten seconds per scene in this initial release; a verified CUDA runtime can use a thirty-second limit. These are resource guards, not performance guarantees. Longer narration is rejected with instructions to split it, rather than truncated. Start with the four-word audition because CPU generation may be many times slower than playback.

## Source and model provenance

SadTalker's official repository states Apache 2.0 licensing. Its model architecture incorporates third-party components; review upstream licenses and weight terms for organizational deployment. The explicit downloader uses official OpenTalker and facexlib GitHub release URLs linked by upstream. It records file size, SHA-256 and whether a publisher digest was available. A locally calculated hash alone does not verify publisher authenticity. No commercial/regulatory compliance is certified here.

The example portrait is an original fictional character created with the built-in image generation tool, not extracted from the supplied video. Asset: `approved_media/presenters/fictional_educator.png`. Prompt: “Realistic fictional Indian male educator, early 30s, navy collared shirt, chest-up, centered frontal face, relaxed closed lips, gray studio background, even light; original identity, no reference-person resemblance, logos or text.” The built-in tool is a one-time asset creation step, not a local image-generation service embedded in this app.

No full-body gesture generation, voice cloning, translation or phoneme-level quality metric is provided by this integration. Choosing a voice never translates the SOP. Keep the recorded-presenter fallback for unsupported systems and verify the final playback before training release.


## Measured result — 18 October 2026

The actual CPU run generated 55 frames at 25 fps (2.2 seconds) from the phrase “Welcome to SOP training.” using Microsoft David and the fictional portrait. Wall time was 764.72 seconds, including invocation overhead; the upstream runtime reported 760.3 seconds. CUDA was not installed in this tested environment, so these are CPU measurements on the target computer, not a GTX 1050 benchmark. The complete video compositor subsequently reused this exact generated animation and driving speech in circular picture-in-picture, without another model run.

Files: `examples/ai_presenter/speaking_presenter.mp4`, `examples/ai_presenter/benchmark.json`, and the composed video selected by `examples/ai_presenter/composed_latest.json`. Contact frames were inspected and show mouth movement with a static body. No phoneme-level sync score or long-form identity consistency evaluation was performed. CPU speed is impractical for long SOP training videos. Do not extrapolate a GPU speedup or advertise full-body performance from this result.
