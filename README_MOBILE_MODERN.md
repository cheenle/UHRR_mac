# Universal HamRadio Remote - Modern Mobile Interface

This directory contains a new mobile-optimized web interface for the Universal HamRadio Remote (UHRR) system, specifically designed for iPhone 15 and other modern mobile devices.

## Features

- **Responsive Design**: Optimized for iPhone 15 screen dimensions and aspect ratio
- **Touch-Optimized Controls**: Large, easy-to-tap buttons with appropriate spacing
- **Safe Area Support**: Proper handling of notches and home indicators
- **Professional Radio Controls**: Full access to radio functions through a mobile-friendly interface
- **PWA Support**: Installable as a standalone app with offline capabilities
- **Modern UI**: Clean, intuitive interface with visual feedback

## Files

- `mobile_modern.html` - Main HTML file for the modern mobile interface
- `mobile_modern.css` - CSS styling with mobile optimizations
- `mobile_modern.js` - JavaScript functionality for radio control
- `manifest.json` - PWA manifest for app-like installation
- `sw.js` - Service worker for offline support
- `test_mobile.html` - Test page to verify functionality

## Key Improvements Over Original Mobile Interface

1. **Enhanced Touch Experience**: Larger touch targets and optimized gesture handling
2. **iPhone 15 Specific Optimizations**: Designed for the latest iPhone screen dimensions
3. **Modern Design Language**: Updated UI with contemporary styling
4. **Improved Performance**: Optimized for faster response times
5. **Better Accessibility**: Enhanced visual feedback and status indicators

## Testing

To test the mobile interface:

1. Open `mobile_modern.html` in a mobile browser
2. Or run the test page `test_mobile.html` to verify all components are present

## Compatibility

- Works alongside the existing `mobile.html` interface (no replacement)
- Compatible with iPhone 15, 14, 13, 12 series
- Works on modern Android browsers
- Supports iPad and tablet devices

## Documentation

- `docs/mobile_modern_interface.md` - Detailed technical documentation
- `docs/iphone15_mobile_interface_analysis.md` - Analysis of iPhone 15 requirements

## Backend Compatibility

The new mobile interface maintains full compatibility with the existing UHRR backend:
- Uses the same WebSocket endpoints (`/WSCTRX`, `/WSaudioRX`, `/WSaudioTX`)
- Supports all existing radio control commands
- Maintains the same authentication and security model