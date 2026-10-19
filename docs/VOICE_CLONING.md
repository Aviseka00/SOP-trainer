# Authorized video-to-voice workflow

Voice studio accepts common video/audio formats and uses FFmpeg to decode a selected 5–180 second segment into a local 16 kHz mono PCM WAV. It rejects silent, short or missing audio; no speaker separation is performed. Source uploads and samples are kept under `.local/voice_samples`. Users preview the exact extracted sample before authorizing cloud transmission.

Creation uses HeyGen `POST /v3/models/audio/voices`, mode `instant`, with inline base64 WAV. The provider's documented 16 MB inline limit is enforced; the maximum extracted sample is under that limit. Explicit speaker permission, authorization reference and provider-usage acceptance are required in the interface. Name, sample hash and consent time are retained in the clone record; credentials are session/environment-only unless separately encrypted by the existing credential manager.

Status is checked using `GET /v3/models/audio/voices/{voice_id}`. ACTIVE clones can generate auditions with `POST /v3/models/audio/tts`. Instant voice requests omit unsupported rate/pitch controls and use expressiveness boost 0.5. Narration is limited to 5,000 characters per scene. Output audio is downloaded only from the existing trusted HeyGen media hosts.

Applying a clone requires a selected HeyGen presenter. The avatar record stores the clone ID, `native_voice_clone` and authorization provenance. Scene approvals and the presenter playback review reset. Rendering synthesizes cloned speech, then calls the existing video endpoint with `audio_url`, excluding `script` and `voice_id`, to animate against that exact speech. Export retains the returned video's speech. Local/Edge draft narration remains separate; this does not install a Windows/Synthesia voice.

Clone and speech submissions are journaled before POST. Unknown outcomes do not cause automatic resubmission. Known speech output can be downloaded again without another synthesis POST. Matching clones, speech and presenter performances are cached. Expired provider media URLs may require provider support/manual recovery; the app does not silently purchase replacement speech after an uncertain request.

Validation on 19 October 2026: full suite with Windows speech enabled ran 67 tests; 66 passed, one optional cached avatar benchmark skipped. Five voice-cloning tests cover real MP4 extraction, silence/missing-track rejection, UI consent enforcement, applying the voice, duplicate/uncertain request handling, speech cache and audio-driven video payloads. Provider calls were mocked; live clone similarity and lip-sync quality were not tested. Compilation and dependency checks passed.

Official API references:

- https://developers.heygen.com/docs/voices/heygen-voice-instant-clone
- https://developers.heygen.com/docs/voices/heygen-voice-speech
- https://developers.heygen.com/audio-to-video
