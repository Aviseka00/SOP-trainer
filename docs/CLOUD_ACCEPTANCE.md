# Actual cloud SOP acceptance test — 18 October 2026

The completed video is `examples/cloud_acceptance/SOP_Cloud_Scientist_Demo.mp4`. Dashboard contains a player under **Watch the completed cloud scientist test**. A reopenable local project is saved as **Cloud scientist — DEMO SOP acceptance** (project ID `76ee6da1851f4d979c42578f4eb57d59`).

## Actual path tested

1. Created a PDF from the bundled fictional hand-hygiene SOP and extracted it using the app's PDF ingestion.
2. Built an eight-point source-linked overview with the app's summary engine. Spoken section prefixes were removed; original instructions/references remained attached.
3. Generated eight real HeyGen Avatar IV performances using the already authorized fictional lab scientist and exact per-scene speech through the connected chat provider. This does not claim that the local app has a HeyGen API key.
4. Downloaded the completed cloud clips for transformation/analysis and imported them into the app's scene-bound cloud-video path. Each clip is bound to the exact narration hash and video checksum.
5. Generated and inspected eight local contextual schematic animations. The preparation scene was deliberately assigned a process card, and a separate hand-wetting template was added to avoid labeling wetting as rinsing.
6. Used the actual app worker/compositor for strict-media export, with each provider clip's own original speech. The result contains 1,235 frames at 30 fps, approximately 41.17 seconds, in 1280×720 MP4, with SRT/VTT subtitles and a source/checksum manifest.

The source PDF is a fictional application demonstration, not a user's operational SOP. Its warnings and overview omissions remain explicit. This is an engineering integration test, not procedural or regulatory approval.

## Synchronization evidence and limits

Decoded the final AAC speech and compared each scene with the normalized waveform used by the compositor. Every scene's best correlation occurred at **0 ms added offset** with **2 ms measurement resolution**; waveform correlations ranged from 0.99855 to 0.99923. This demonstrates preservation of the cloud video's speech timing through local composition.

Sampled eight full/face/hand frames from each cloud clip. The fictional identity stays consistent in these samples, lips change shape, eyes change openness/blink, and both hands gesture. The existing local 98-point face model was also used to measure mouth and eye activity: 112 sampled frames across the eight scenes (54 in scene 1; 8–9 in others). Hand-region pixel changes are recorded separately.

These checks **do not independently certify phoneme-to-viseme correctness, intentional eye targets or meaning-specific hand gesture timing**. Original-audio preservation and visible activity alone cannot establish those claims. Minor synthetic facial/finger artifacts remain possible; full audiovisual playback review is still needed for a production release. Reports explicitly distinguish these limits from the technical timing pass.

Evidence is in `examples/cloud_acceptance/acceptance_report.json`, contact sheets, the visual review sheet and the original sample PDF. More detailed working evidence remains under `outputs/validation/cloud_acceptance`.

## Actual provider checks

The previous Python TLS failures were resolved using truststore's native certificate context with certificate and hostname verification enabled. Both encrypted Synthesia and Kling keys passed real read-only API checks.

One live five-second Kling generation was attempted through the app worker. The API returned HTTP 429. A separate free usage query returned zero active resource packages and zero reported remaining quantity. The rejected task was not repeatedly resubmitted; local animations were used explicitly. This does not assert that Kling generation succeeded.

Synthesia live presenter generation was not substituted for the chosen fictional scientist; its separate avatar selection remains necessary. No Synthesia production video was created in this test.

## Cloud import in the app

Presenter studio now accepts one externally rendered cloud video per scene. Confirm the exact spoken narration when attaching it. The app extracts the video's original audio and refuses a missing script match or changed video checksum. This allows chat-connector and provider-website renders to participate in local composition without pretending the app has access to the connector's OAuth credentials.
