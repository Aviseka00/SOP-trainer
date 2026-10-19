# Actual cloud acceptance and regressions — 18 October 2026

Final full suite: **54 tests passed, no skips**, 45.480 seconds, with SOP_TEST_SPEECH=1 and SOP_TEST_AVATAR=1.

The first regression run found a cloud presenter type-label mismatch introduced while adding imported clips. The label was corrected; the complete final suite above passed.

Live checks: Synthesia read API accepted the saved encrypted key; Kling task-list API accepted the saved encrypted key. Connections now use truststore native TLS with hostname and certificate verification enabled. A live Kling clip submission returned HTTP 429 and no task ID. Its usage endpoint reported zero active packages in the requested range. No repeated paid Kling submission was performed.

Eight actual HeyGen Avatar IV scientist videos were generated through the connected provider using source-derived speech, then brought into the local app through the implemented cloud import adapter. No fake API key or static-video substitute was used. Eight local conceptual animations were reviewed against the bundled sample PDF, then rendered through the real worker/compositor.

Actual final output: 1,235 frames, 30 fps, 1280×720, approximately 41.17 seconds. All eight scene waveform correlations peaked at 0 ms compositor-added offset with 2 ms resolution; correlations were 0.99855–0.99923. The MP4 decoded successfully and SRT/VTT/source/checksum artifacts were produced.

Visual contact sheets and 112 sampled face-landmark frames show changing mouth/eye geometry and moving hands. This is activity evidence; it does not independently validate original phoneme/viseme synchronization or meaning-specific gesture timing. Those claims remain outside the technical pass. See `CLOUD_ACCEPTANCE.md` and the example acceptance JSON for the precise scope.

The end-to-end source was the bundled fictional sample SOP converted to PDF, not an operational SOP supplied by the user.
