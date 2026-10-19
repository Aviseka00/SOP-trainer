# Validation — 18 October 2026

Full suite: `.venv/Scripts/python.exe -m unittest discover -s tests -v`, with SOP_TEST_SPEECH=1 and SOP_TEST_AVATAR=1: **42 tests passed, no skips**, 42.288 seconds. Executed outside the restricted Windows sandbox for Streamlit and SAPI compatibility.

After adding the final required `type: avatar` API discriminator and deterministic Idempotency-Key header, the five cloud-adapter tests passed again in 1.714 seconds.

Covered: source-linked key-point selection; numeric and prohibition retention; stale-source refusal; rejected model omissions; summary-to-animation UI planning; cloud configuration and session credential persistence without project serialization; journal recovery preventing duplicate paid submissions; media-host validation; existing render/layout/animation and project-integrity tests; installed Windows speech; cached real SadTalker composition.

The cloud-composition test uses an existing local talking-presenter fixture and a mocked provider call, then performs real FFmpeg rendering. It verifies that separate local TTS is not called, the selected provider audio checksum appears in the timeline and the manifest identifies cloud speech.

No live HeyGen API key was available to the local app, so API authentication, entitlement, cloud rendering latency, returned-media download and this new pipeline's final generated gesture quality are unverified. The separate chat-connector scientist sample does not count as an app API integration test.

Optional Ollama speech rewriting is covered for malformed/omitted points, but no live local model rewrite was benchmarked in this change.
