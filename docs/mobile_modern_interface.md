# Modern Mobile Interface for iPhone 15 and Modern Browsers

## Overview

This document describes the mobile-optimized web interface designed specifically for iPhone 15 and other modern mobile browsers. The interface maintains full compatibility with the existing MRRC backend while providing an enhanced user experience for mobile users.

**Version**: v4.5.1 (2026-03-06)

## Features

### Responsive Design
- Optimized for iPhone 15 screen dimensions and aspect ratio
- Safe area insets support for notch and home indicator
- Touch-optimized controls with appropriate sizing
- Landscape and portrait orientation support

### Modern UI Components
- Large PTT button positioned for comfortable reach
- Frequency display with clear digit separation
- Visual feedback for active states
- Dark mode support
- Real-time power/SWR display (ATR-1000)

### Performance Optimizations
- Touch event handling optimized for minimal latency
- Efficient WebSocket connections
- Service worker for offline support
- PWA capabilities for app-like experience

### Professional Features
- Full radio control functionality
- S-Meter visualization
- Quick access to essential functions
- Status indicators for connection and transmission
- TX Equalizer (3-band)
- TUNE button for antenna tuner
- Band/Mode selection menus

## Technical Implementation

### File Structure
```
www/
├── mobile_modern.html     # Main HTML file (iPhone 15 optimized)
├── mobile_modern.css      # Modern CSS with mobile optimizations
├── mobile_modern.js       # JavaScript functionality
├── manifest.json          # PWA manifest file
└── sw.js                  # Service worker for offline support
```

### Key Technologies
- CSS Grid and Flexbox for responsive layout
- CSS Custom Properties for theming
- Web Audio API for audio processing
- WebSocket API for real-time communication
- Service Worker API for PWA support
- Touch Events API for mobile interaction
- Vibration API for haptic feedback
- Safe Area Insets for notch support

### Mobile-Specific Optimizations
1. **Safe Area Support**: Uses `env(safe-area-inset-*)` for proper spacing around notches
2. **Touch Target Sizes**: All interactive elements are at least 44px for comfortable tapping
3. **Prevent Zoom**: Viewport settings prevent accidental zooming
4. **Fast Clicks**: Touch events replace mouse events for faster response
5. **Haptic Feedback**: Vibration API provides tactile feedback
6. **Orientation Handling**: Adapts to device orientation changes

## Compatibility

### Device Support
- iPhone 15 series (primary target)
- iPhone 14, 13, 12 series
- Android devices with modern browsers
- iPad and tablet devices

### Browser Support
- Safari (iOS 16+)
- Chrome (Android/iOS)
- Firefox (Android/iOS)
- Edge (Android/iOS)

### Backward Compatibility
The new interface coexists with the existing mobile interface (`mobile.html`) to ensure no disruption to current users.

## Key Features Detail

### 1. PTT Button
- Large touch target (80px+ diameter)
- Haptic feedback on press
- Visual state indication
- Touch event optimization

### 2. Frequency Display
- Large, clear digit display
- Frequency adjustment buttons (optimized layout)
  - Top row: +50, +10, +5, +1 (increase frequency)
  - Bottom row: -50, -10, -5, -1 (decrease frequency)
  - Unified gray background, bold white text
  - Intuitive "up-add, down-subtract" layout
- Band selection menu
- Real-time update from radio

### 3. S-Meter
- Visual signal strength indicator
- S0 to S9+60dB range
- Real-time update

### 4. Power/SWR Display (ATR-1000)
- Real-time forward power (0-200W)
- SWR indicator (1.0-9.99)
- Color-coded status (green/yellow/red)
- <200ms display latency

### 5. TX Equalizer
- 3-band equalizer (Low/Mid/High)
- 4 presets: Default, HF Voice, DX Weak, Contest
- Cookie persistence

### 6. TUNE Button
- Long-press to transmit 1kHz tone
- For antenna tuner adjustment
- Real-time power feedback

### 7. Menu System
- Band Selection (160m to 10m)
- Mode Selection (USB, LSB, AM, FM)
- Audio Controls (AF Gain, MIC Gain, Squelch)
- TX Equalizer settings
- About information

## Testing

### Automated Tests
Run `./dev_tools/test_mobile.sh` to verify:
- All required files exist
- HTML structure is correct
- CSS features are implemented
- JavaScript functionality is present

### Manual Testing
1. Open `mobile_modern.html` in a mobile browser
2. Verify layout on different screen sizes
3. Test PTT button responsiveness
4. Check orientation changes
5. Verify WebSocket connectivity
6. Test offline functionality with service worker
7. Verify ATR-1000 power display during TX

## Deployment

### Server Configuration
No special server configuration is required. The files can be served as static content.

### SSL Requirements
For full PWA functionality, the site should be served over HTTPS.

### Caching Strategy
The service worker implements a cache-first strategy for static assets and a network-first strategy for dynamic content.

## Troubleshooting

### Common Issues
1. **PTT Button Not Responding**: Check browser permissions for microphone access
2. **Connection Failed**: Verify WebSocket server is running and accessible
3. **Layout Issues**: Ensure viewport meta tag is present in HTML
4. **Offline Mode Not Working**: Check service worker registration in browser dev tools
5. **Power/SWR Not Displaying**: Check ATR-1000 proxy is running
6. **Frequency Not Updating**: Verify rigctld connection

### Debugging
Use browser developer tools to inspect:
- Console logs for JavaScript errors
- Network tab for WebSocket connections
- Application tab for service worker status
- Elements tab for CSS layout issues

## Performance Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Page Load | <2s | ~1.5s |
| PTT Response | <50ms | ~40ms |
| Audio Latency | <100ms | ~65ms |
| Power Display | <200ms | ~150ms |
| Memory Usage | <50MB | ~30MB |

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v4.5.0 | 2026-03-06 | ATR-1000 stable, dual time protection |
| v4.5.1 | 2026-03-06 | Frequency tuning button layout optimization |
| v4.4.0 | 2026-03-05 | ATR-1000 real-time display fix |
| v4.3.0 | 2026-03-04 | ATR-1000 architecture separation |
| v4.2.0 | 2026-03-02 | TX Equalizer integration |
| v4.1.0 | 2026-03-01 | Project rebrand to MRRC |
| v4.0.0 | 2026-03-01 | TX→RX latency optimization |
| v3.0.0 | 2024-12 | Initial mobile modern interface |

## Future Enhancements

### Planned Features
- Enhanced digital mode support
- Advanced logging capabilities
- Customizable layouts
- Voice commands
- Biometric authentication

### Performance Improvements
- Audio processing optimizations
- Battery usage reduction
- Memory management enhancements
- Connection reliability improvements

---

*This document describes the MRRC v4.5.1 mobile interface.*
*Last updated: 2026-03-06*
