# Audio Fix Summary

## Issue
Audio was not working in the old style browser interface after recent updates that changed the sample rate from 8000 to 24000.

## Root Cause
The sample rate mismatch between the old browser interface (expecting 8000 Hz) and the updated code (using 24000 Hz) was causing audio playback failures.

## Changes Made

1. **Updated mobile.js:**
   - Changed `audioRXSampleRate` from 24000 to 8000
   - Updated filter frequency from 22000 to 4000 Hz to match 8kHz sample rate
   - Updated comment to reflect 8kHz sample rate

2. **Updated mobile_audio_direct_copy.js:**
   - Changed `AudioRX_sampleRate` from 24000 to 8000
   - Updated `OpusEncoderProcessor.sampleRate` from 24000 to 8000
   - Updated `OpusEncoderProcessor.frameSize` from 960 to 160 (20ms at 8kHz)
   - Updated filter frequency from 12000 to 4000 Hz to match 8kHz sample rate
   - Updated comments to reflect 8kHz sample rate

## Verification
The changes have been made to ensure compatibility with older browsers that may not support higher sample rates. The audio should now work correctly in the old style browser interface.