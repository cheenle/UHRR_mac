## Progress
### Done
- Created AGENTS.md with verified guidance on entrypoints, commands, architecture, subprojects, port mismatches.
- Analyzed full RX/TX audio chain: sample rate flow, half-duplex mechanism, WDSP integration, Opus encoding, frontend playback engines.
- Implemented 7 optimizations:
  1. Recording downsampling: 3-sample average anti-alias filter (replaced naive `[::3]` slice).
  2. RX Opus encoder configured via `configure_for_voip(bitrate=28000, complexity=8, fec=True, packet_loss_perc=15, dtx=True)`.
  3. Frontend TX Opus defaults in `opus_codec.js`: complexity=8, bitrate=28kbps, VBR=ON, FEC=ON(15%), DTX=ON, HPF=OFF.
  4. Pre-AGC bypass when WDSP AGC active (prevents AGC fighting).
  5. TX level normalization with gain smoothing (attack α=0.5, release α=0.05).
  6. Adaptive Opus bitrate by client queue depth: 32kbps (q<5), 24kbps (q<15), 16kbps (q≥15).
  7. Frontend TX Opus FEC: inband_fec=1, packet_loss_perc=15.
- Fixed bug: `controls.js` had no-op JS property assignments (`this.opusEncoder.bitrate = 28000`) that did nothing on the WASM wrapper — moved settings into `opus_codec.js` constructor via real `_opus_encoder_ctl` calls.
- Improved: RX encoder uses Python wrapper's `.bitrate` setter (maps to `_opus_encoder_ctl`), so adaptive bitrate works correctly.

### In Progress
- (none)

### Blocked
- (none)

## Key Decisions
- Opus bitrate 28kbps chosen as quality/bandwidth sweet spot for 16kHz speech (vs 20kbps prior).
- Adaptive bitrate uses client Wavframes queue depth as network proxy; thresholds 5/15 balance stability and responsiveness.
- TX gain smoothing uses asymmetric attack/release to prevent pumping while catching overloads fast.
- Frontend `OpusEncoder` (WASM wrapper) hard-codes defaults in constructor; no runtime setter props — all tuning done inside `opus_codec.js` module.
- Backend Python OpusEncoder exposes `.bitrate` as a real setter (maps to ctypes `_opus_encoder_ctl`) — adaptive bitrate works there.

## Next Steps
- (none — all requested work is complete)

## Relevant Files
- `AGENTS.md`: new instruction file for OpenCode sessions.
- `audio_interface.py`: RX capture/encode/TX playback with all audio processing; modified for opts 1,2,4,5,6.
- `www/controls.js`: frontend TX Opus encoder processor; no-op props removed.
- `www/modules/opus_codec.js`: Opus WASM encoder/decoder; optimized defaults in constructor.
- `www/audio_rx.js`: frontend RX playback (BufferSourceNode engine V5.2).
- `www/tx_button_optimized.js`: TX button timing and PTT safety logic.
- `DSP.md`, `AOD.md`, `docs/PTT_Audio_Postmortem_and_Best_Practices.md`: architecture documentation.
- `CLAUDE.md`: pre-existing guidance (superseded by AGENTS.md for compact gotchas).
