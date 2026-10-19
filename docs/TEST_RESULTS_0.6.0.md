# Provider integration validation — 18 October 2026

Full regression suite with SOP_TEST_SPEECH=1 and SOP_TEST_AVATAR=1: **51 tests passed, no skips**, 52.896 seconds.

After the final worker credential isolation change and an additional isolation test, all **9 provider tests passed**, 1.094 seconds. These exercise current-user Windows DPAPI encryption/decryption, absence of plaintext keys in the stored file, provider-specific environment filtering, absence of credentials in job request JSON, unknown paid-submission recovery, credential-required submission gates, documented Kling bearer authentication, and Synthesia/Kling payload and provenance handling.

UI tests verify that Synthesia can be selected, keys stay outside project JSON, key values survive page navigation in session memory, and Kling generation remains disabled until the operator authorizes sending contexts and consuming provider credits.

Synthesia and Kling cloud calls were mocked. Existing local video was decoded with FFmpeg to verify provider media handling; no paid jobs were created. No actual API credentials were supplied. Provider authentication, plan entitlement, cloud latency, CDN compatibility and generated quality still need a live test in the app.

Streamlit health endpoint returned `ok` after the update. Release ZIP integrity is checked by the packaging script; encrypted credential storage is excluded from the package.
