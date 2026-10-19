# SOP to fictional scientist training

1. In **Source document**, upload PDF, DOCX or TXT, then extract and save the source. Scanned PDF files need OCR outside this app.
2. Open **Summary & key points**, choose a target length and generate the speech draft. The default is extractive selection: source sentences, in order, with references. It is a training overview, not a complete procedural replacement. Critical/prohibited and numeric instructions can make it longer than the target.
3. Edit each key point, its speech and animation context. An optional installed Ollama model can rewrite the selected speech; no model is downloaded automatically. Compare the result with the full SOP, including conditions and units. Save edits before building scenes.
4. Accept the overview omissions and click **Build scenes & contextual animations**. Open **Visual generation** to monitor, inspect and approve the resulting schematic animations. Templates cover supported topics; unmatched topics use source process cards. These are explanatory graphics rather than photorealistic procedural simulations.
5. In **Presenter studio**, expand **HeyGen cloud presenter setup**. Enter your API key in the password field or configure HEYGEN_API_KEY before starting the app. A chat connection does not grant API access to this local application. Keys entered in the app remain in that Streamlit session's memory and child-worker environments, not project downloads, saved project JSON or job request files.
6. Select an accessible fictional avatar look and compatible voice. The defaults refer to the fictional scientist created in the connected workspace; another API workspace may require different IDs. Read and enable the cloud narration/credits checkbox, then select **Use HeyGen scientist for this project**. This applies side-by-side composition to existing scenes. New cloud renders send scene speech to HeyGen and consume provider API credits.
7. Approve current scenes in **QA review**, then render in **Export center**. Cloud video is generated per scene; its own audio drives the final timeline, captions and contextual visual duration. The normalized audio changes loudness, not timing. No independent local TTS is substituted.
8. Inspect the finished video for pronunciation, lips, gaze, hand anatomy, gesture relevance and source accuracy before distributing it. Speech-matched gesture prompts are guidance, not guarantees of exact semantic pointing or perfect synchronization.

The existing local SadTalker path remains face/head-only and is slow on this CPU. Cloud credentials are optional for summary planning, schematic generation and local rendering.

## Recovery and limits

Cloud jobs store submission IDs under cache/heygen. A resumed render reuses an existing ID rather than paying for the same request again. An interrupted POST with no confirmed ID requires checking the provider dashboard before any manual retry. Canceling a local render stops local polling; it does not promise cancellation or refund of provider processing. Generated media is cached and checksum-validated.

Narration must already be in the intended language. Voice or locale selection does not translate a source document. Summary editing, model output and generated visuals all require review; automatic regulatory approval is not claimed.

## API reference and validation

Implementation follows the official HeyGen v3 reference: https://github.com/heygen-com/heygen-stack/blob/main/references/api-reference.md and https://developers.heygen.com/reference/create-video . The adapter uses POST /v3/videos and GET /v3/videos/{id} with Avatar IV, avatar/voice IDs, script and motion direction.

Live API generation in this app is not yet credential-tested. Offline tests exercise source preservation, stale-source handling, secret exclusion, paid-job recovery and real FFmpeg composition using a local presenter fixture with the cloud call mocked. This is distinct from the actual scientist sample generated through the chat connector.
