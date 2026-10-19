# Video providers

Open **AI providers** to enter developer API keys. Do not enter website passwords. A website subscription or chat connection alone does not establish API entitlement.

| Service | Implemented role | Required credential |
|---|---|---|
| HeyGen | Avatar IV presenter, configured in Presenter studio | HeyGen API key |
| Synthesia | Presenter scenes using an accessible Synthesia avatar; select in AI providers | Legacy (v2)-scoped API key |
| Kling AI | Text-to-video contextual clips in Visual generation | Current developer API key used as a Bearer token |

Kling setup targets the current official Singapore API endpoint. Legacy Access Key/Secret Key pairs are not accepted by this setup; obtain a current developer API key from the official console. Synthesia Interactive Avatars keys are not accepted by its v2 Video API.

## Credential storage

Keys remain in Streamlit session memory unless **Save keys encrypted for my Windows account** is clicked. Saved values use Windows DPAPI current-user protection in `.local/credentials.dpapi`. Only encrypted bytes are written. There is no plaintext fallback. This file is excluded from source control and release packaging. The Windows account can unlock its stored keys; this does not protect against software already running as that user.

**Forget saved and session keys** removes the saved file and clears session keys. Environment-provided credentials must be removed from the app process environment separately. Windows encrypted storage is not portable to another user or computer; re-enter keys there.

## Synthesia

Enter an avatar ID available in your Synthesia account. This adapter does not upload or transfer the fictional HeyGen scientist to Synthesia. Select a fictional avatar or one you are authorized to use. The implemented request uses the avatar's default voice. Voice override, custom photo-avatar creation and gesture control are not implemented for Synthesia.

Test mode is enabled by default and produces a watermarked preview where supported by the provider. Turn it off explicitly for production generation. Narration is submitted as `scriptText`; final composition extracts and uses the provider video's own audio instead of replacing it with local TTS. Visibility is private. Check read access using the no-generation button before attempting an export.

## Kling visuals

In **Visual generation**, select **Kling AI**, choose a supported model and 5- or 10-second clip length, then authorize sending the selected scene contexts and using provider credits. Generate one scene first to assess fidelity before generating every scene. The full source document is not uploaded; the animation context derived from your scene is sent. Both controls are user-triggered; no hidden provider switching or paid fallback is performed.

Kling output is stored as a draft in the local media library. Inspect it against the SOP before approval. Generated footage may contain invented geometry or incorrect technique. Requests ask for silent concept clips; scene narration comes from your selected presenter or voice. A short clip may loop within a longer narrated scene in the existing compositor. Precise step-timed visual choreography is not implemented.

## Recovery

Task IDs and request hashes are stored under provider-specific cache directories. Unknown submission outcomes stop rather than automatically issuing another paid request. A known task can be polled again without resubmission. Canceling the local worker does not cancel or refund cloud processing. Downloaded assets are bounded to 500 MB and validated with FFmpeg before use. An unsupported provider CDN host fails explicitly rather than following an arbitrary URL.

## Official references

- Synthesia API quickstart and key scope: https://docs.synthesia.io/reference/synthesia-api-quickstart
- Synthesia video creation: https://docs.synthesia.io/reference/create-video
- Kling developer setup and API key: https://kling.ai/document-api/guides/get-started/quick-start
- Kling text-to-video request and task polling: https://kling.ai/document-api/api/video/3-0-omni/text-to-video/legacy

Update, 18 October 2026: both saved provider keys passed real read-only checks after the native TLS fix. One live Kling generation attempt returned HTTP 429; its usage query reported no active packages. Synthesia live video generation remains untested. A separate actual fictional HeyGen scientist test completed through scene-bound cloud import and the app compositor; see `CLOUD_ACCEPTANCE.md`. Automated provider tests still use mocked cloud calls and do not establish credit entitlement or semantic performance quality.
