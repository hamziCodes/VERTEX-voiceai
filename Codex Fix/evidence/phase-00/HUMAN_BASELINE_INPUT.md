# Human baseline input required

H01 and H02 were resolved on 2026-10-15. Per-run audio-device details still belong in local measurement artifacts rather than source control.

## Recorded decision

- Product surfaces: web browser voice agent and calling agent through the Telnyx telephony layer.
- Browser reference: Windows 11 Home 10.0.26300 build 26300, Intel Core i5-13420H, 15.6 GB RAM, Chrome 150.0.7871.115.
- Telephony reference: offline 8 kHz G.711 μ-law codec and packet simulation first; a real Telnyx sandbox call remains a separate paid/live approval in Phase 12.
- Speech corpus: pinned FLEURS validation clips for `en_us`, `ur_pk`, and `ar_eg`; existing legacy `minglish_test.wav` may be used for code-switch timing but not accuracy until its transcript is confirmed.
- Downloaded FLEURS audio and transcripts remain Git-ignored. Only the downloader, revision, selection rules, tests, and attribution are committed.

## Per-run H01 fields

- Operating-system edition and build:
- CPU model:
- Installed RAM:
- Power mode, plugged in or battery:
- Browser name and exact version:
- Browser audio-output device:
- Browser microphone/input device:
- Headset/speaker transport, wired/Bluetooth/USB:
- Test location/network type for later approved live tests:
- Background-load constraints:

Browser version can be copied from the browser's About page. Windows OS build can be copied from `winver`. Do not paste machine IDs, account names, IP addresses, tokens, or credential values.

## Additional H02 fixtures

Only add recordings beyond the pinned FLEURS subset when a test needs:

- natural Urdu/English code switching with a confirmed transcript;
- natural mid-sentence pauses;
- low volume;
- ordinary background noise.

For each added file, record language, expected transcript, sample rate, channels, encoding, duration, and whether it may be committed. Provider accuracy and listening quality remain later verification activities; Phase 00 makes no runtime-provider claim.
