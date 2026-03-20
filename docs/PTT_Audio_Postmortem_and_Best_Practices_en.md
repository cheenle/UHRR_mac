# MRRC Transmit (TX) / Receive (RX) Stability Postmortem and Best Practices

This document systematically reviews the typical instability issues encountered when using MRRC in browsers, providing engineering countermeasures and a "working stable baseline." Focus is on achieving 100% reliable TX initiation and low-jitter RX.

**Version**: V4.9.1 (2026-03-15)

---

## 1. Phenomenon and Root Cause Summary

### 1.1 PTT Pressed No Transmit, Flashes on Release
- **Phenomenon**: No transmit during TX button hold, radio "flashes" momentarily on release.
- **Root cause chain**:
  1) Frontend timing issue: Sends `setPTT:true` first, but TX audio channel not initialized (no `m:` sent) or first packet didn't arrive in time.
  2) Backend judgment method: Only uses "time threshold" (e.g., no audio within 0.5s → PTT auto turns off), sensitive to network/thread jitter.
  3) Race/delay: `wsAudioTX` not OPEN or audio encoder first frame takes time, causing "gap window" between "PTT → first packet."

### 1.2 TX Occasional Failure (1~2 out of 10 times)
- **Root cause**: Light version of 1.1 - gap slightly larger than backend threshold causes mistaken turn-off.

### 1.3 RX Audio Lag/Jitter, More Obvious After Transmit
- **Root cause**: RX buffer uncontrolled depth, accumulated; ScriptProcessor main thread jitter; sample rate inconsistency causing resampling jitter; TX end not clearing tail buffer.

### 1.4 TX to RX Switch Delay (2-3 seconds)
- **Phenomenon**: After releasing PTT button, 2-3 second noticeable delay when switching from TX mode to RX mode.
- **Root cause chain**:
  1) Buffer clear failure: Attempts to clear RX audio buffer on PTT release but references wrong variable name
  2) PTT command duplicate sending: Multiple event handlers may cause same PTT command sent repeatedly
  3) PTT confirmation mechanism delay: Unnecessary delay and retry mechanism after PTT command sent
  4) RX audio buffer depth too large: Buffer depth set too large for stability guarantee

### 1.5 ATR-1000 Power/SWR Display Delay
- **Phenomenon**: Power/SWR display delay on mobile during transmit.
- **Root cause chain**:
  1) Tornado's `IOLoop.add_callback()` batches messages
  2) WebSocket `write_message()` must be called in main thread
  3) `ScriptProcessorNode` blocks main thread affecting WebSocket message processing

### 1.6 Transmit Volume Too Low or Distorted After Amplification
- **Root cause**: Frontend has fixed `/10` attenuation; after removal, if peak not controlled, easy to clip.

### 1.7 TLS Certificate Error (BAD_END_LINE/Incomplete Chain)
- **Root cause**: CR/LF mixing, line-end backslash; fullchain includes root certificate; not using `SSLContext` standard loading.

---

## 1.8 V4.5.4 Audio Processing Optimization
- **Phenomenon**: High CPU usage during TX, affecting ATR-1000 response.
- **Optimization measures**:
  1) **Frame length optimization**: 40ms → 20ms (WebRTC recommended value)
  2) **Encoding complexity**: 10 → 5 (balance CPU and quality)
  3) **DTX silence detection**: On (no encoding during silence)
- **Effects**:
  - CPU usage reduced by ~30%
  - Processing frequency increased from 25 times/s to 50 times/s
  - Near-zero CPU usage during silence

---

## 2. Implemented Countermeasures (Code Level)

### 2.1 TX Initiation "Deterministic Flow" (Frontend + Backend Coordination)
- **Goal**: Press → immediate PTT, while ensuring backend definitely receives audio within timeout/counting window to avoid mistaken turn-off.
- **Frontend** (`www/tx_button_optimized.js`):
  1) Press: Immediately `setPTT:true` (highest priority)
  2) Parallel: `toggleRecord(true)` sends `m:rate,encode,op_rate,op_frm_dur` (TX_init)
  3) Warmup: Immediately send 3 warmup frames (one frame every 3ms) to ensure continuous audio within first second
  4) Confirmation: Add confirmation mechanism after PTT command, max 2 retries to ensure command arrives
  5) Release: `s:` (stop/clear tail) → `setPTT:false`, immediately switch back to RX
- **Backend** (`MRRC`):
  - Changed from "time threshold" to "missed frame count timeout": Check every 0.2s, turn off PTT only after 10 consecutive missed audio frames; reset count when frame received.
  - Added retry mechanism for PTT command execution: Max 3 attempts to ensure PTT command succeeds.
  - In control path `WS_ControlTRX.on_message`, `setPTT` fast processing, immediately broadcast `getPTT:<state>`.

### 2.2 RX Low-Jitter Playback
- Introduced `AudioWorkletNode` (`www/rx_worklet_processor.js`) for audio thread playback:
  - Target depth zone: 16/32 (more stable can be 32/64, lower latency can be 2/20)
  - Too deep truncate tail, too shallow pad zeros.
- `controls.js` controls depth of `AudioRX_audiobuffer`, clears tail at TX end to avoid lag accumulation.

### 2.3 TX Input Gain and Soft Limiting
- Cancel fixed `/10` attenuation, change to 1:1 input;
- Use `MIC GAIN` slider with backend/sound card gain for fine-tuning;
- If needed protection, add soft limiting before encoding (-3 dBFS).

### 2.4 TLS Certificate Chain and Loading
- Only concatenate "server certificate + intermediate certificate" as `fullchain.pem`;
- Unify LF, remove line-end backslash;
- Use `ssl.SSLContext.load_cert_chain(certfile=fullchain, keyfile=key)`.

### 2.5 TX to RX Switch Delay Optimization
- Fixed buffer clear: Corrected wrong buffer variable reference in `tx_button_optimized.js`, ensure flush command correctly sent to AudioWorkletNode on PTT release
- Added PTT debounce mechanism: Prevent duplicate PTT command sending, reduce system burden
- Optimized PTT confirmation mechanism: Reduced initial delay (50ms→20ms), retry interval (100ms→50ms), retry count (3→2)
- Adjusted RX audio buffer depth: Changed from default 6/12 frames to 3/6 frames, config from 32/64 frames to 16/32 frames, balance latency and stability
- **Effect**: TX to RX switch latency optimized from 2-3 seconds to <100ms

### 2.6 ATR-1000 Real-time Display Optimization
- **Backend batch broadcast**: 50ms batch collection, broadcast only latest data
- **Thread safety**: Use `IOLoop.add_callback()` to ensure main thread WebSocket write
- **Frontend dual time protection**: Ensure minimum 500ms interval for sync requests
- **Connection warmup**: Pre-establish connection on page load, PTT response <200ms
- **Effect**: Power/SWR display latency optimized from 2-5 seconds to <200ms

---

## 3. Working Stable Baseline (Recommended Default)
- Sampling/Encoding: End-to-end 16 kHz; Int16 PCM (50% bandwidth optimization)
- RX Worklet buffer: 16/32 (optimized balance latency and stability, was 32/64)
- Backend timeout: Missed frame count 10×200ms (≈2s), reset when frame received
- TX input: 1:1 gain, soft limiting if needed (recommend keeping control)
- TLS: `fullchain.pem` (server+intermediate), `<domain>.key`, `SSLContext` loading
- TX to RX switch: Optimized latency <100ms (was 2-3 seconds)
- ATR-1000 display: Optimized latency <200ms (was 2-5 seconds)

> Under this baseline, TX presses to transmit immediately; RX has low jitter, stable latency; TLS compatible with mainstream browsers; TX to RX switch near real-time; ATR-1000 power real-time display.

---

## 4. Operation/Troubleshooting Quick Reference
- Pressed no transmit, flashes on release:
  - Using "press immediately PTT + parallel TX_init + immediately send warmup frames"?
  - Is miss_count threshold too low (now 10 checks, each 200ms)?
- RX stuttering/latency growth:
  - Increase Worklet buffer (16/32→32/64); fix 16 kHz; limit RX ring buffer length
- Transmit volume:
  - Fine-tune with `MIC GAIN`/sound card output; if distortion, add soft limiting or reduce `MIC GAIN`
- TX to RX switch delay:
  - Check if correctly referencing `AudioRX_source_node` variable in `tx_button_optimized.js`
  - Confirm PTT debounce mechanism working properly
  - Verify RX audio buffer depth settings appropriate
- ATR-1000 power not displaying:
  - Check if proxy running: `ps aux | grep atr1000_proxy`
  - Check proxy log: `tail -f atr1000_proxy.log`
  - Check Unix Socket: `ls -la /tmp/atr1000_proxy.sock`
- Certificate error:
  - Only concatenate server+intermediate certificate; fix line endings; use `SSLContext`; verify chain with `openssl s_client`
- Port occupied:
  - `lsof -iTCP:<port> -sTCP:LISTEN` to clean old processes, or use daemon tool to ensure single instance

---

## 5. Further Optimization Suggestions
- **Frontend**:
  - Display TX/RX bitrate, buffer depth, miss_count, PTT status
  - PTT status real-time display implemented, can consider adding more status detail display
  - Further optimize PTT button touch response and event handling
- **Backend**:
  - First frame "protection period": Higher tolerance within 200ms after PTT just opened,叠加 with counting method
  - Log statistics by second, reduce noise
  - Consider dynamically adjusting RX buffer depth to adapt to different network conditions
- **Codec**:
  - 20ms short frame for low latency需求, with smaller buffer, but jitter tolerance decreases
  - Continuously monitor TX to RX switch latency optimization effect, further adjust based on user feedback

---

## 6. Performance Metrics Summary

| Metric | Target | V4.5 Measured | Status |
|--------|--------|---------------|--------|
| PTT Response Time | <50ms | ~40ms | ✅ Met |
| End-to-End Audio Latency | <100ms | ~65ms | ✅ Met |
| TX→RX Switch Latency | <100ms | <100ms | ✅ Met |
| Power Display Latency | <200ms | <200ms | ✅ Met |
| PTT Reliability | 99%+ | 99%+ | ✅ Met |
| ATR-1000 Stability | Stable | Stable | ✅ Met |

---

## 7. References and Acknowledgments
- Upstream project and documentation inspiration: F4HTB/Universal_HamRadio_Remote_HTML5 (Wiki)
  - https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5/wiki

---

*This document is updated based on MRRC V4.9.1 stable version.*
*Last updated: 2026-03-06*
