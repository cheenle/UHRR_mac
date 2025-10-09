// Touch Enhancements for UHRR Interface
// Adds better touch support for all interactive elements

document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing touch enhancements...');
    
    // Add touch support to all buttons and interactive elements
    enhanceTouchControls();
    
    // Add viewport meta tag if not present
    ensureViewportMeta();
});

function enhanceTouchControls() {
    // Get all interactive elements
    const buttons = document.querySelectorAll('button, .button_unpressed, .button_pressed, .button_mode, [onclick], [onmousedown]');
    const inputs = document.querySelectorAll('input[type="range"], input[type="button"], input[type="checkbox"]');
    
    console.log(`Enhancing ${buttons.length} buttons and ${inputs.length} inputs for touch`);
    
    // Enhance buttons
    buttons.forEach(button => {
        // Remove existing mouse events to prevent conflicts
        const mouseDownHandler = button.onmousedown;
        const mouseUpHandler = button.onmouseup;
        const clickHandler = button.onclick;
        
        // Store original handlers
        button._originalMouseDown = mouseDownHandler;
        button._originalMouseUp = mouseUpHandler;
        button._originalClick = clickHandler;
        
        // Remove existing handlers
        button.onmousedown = null;
        button.onmouseup = null;
        button.onclick = null;
        
        // Add touch events
        button.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Visual feedback
            this.classList.add('touch-active');
            
            // Haptic feedback
            if (navigator.vibrate) {
                navigator.vibrate(20);
            }
            
            // Trigger original mouse down handler if it exists
            if (this._originalMouseDown) {
                this._originalMouseDown.call(this, e);
            }
            
            // Trigger original click handler if it exists (for elements that only have onclick)
            if (this._originalClick && !this._originalMouseDown) {
                this._originalClick.call(this, e);
            }
        }, { passive: false });
        
        button.addEventListener('touchend', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Remove visual feedback
            this.classList.remove('touch-active');
            
            // Trigger original mouse up handler if it exists
            if (this._originalMouseUp) {
                this._originalMouseUp.call(this, e);
            }
            
            // Trigger original click handler if it exists (for elements that only have onclick)
            if (this._originalClick && !this._originalMouseUp && !this._originalMouseDown) {
                this._originalClick.call(this, e);
            }
        }, { passive: false });
        
        // Add mouse events for desktop compatibility
        if (this._originalMouseDown) {
            button.addEventListener('mousedown', this._originalMouseDown);
        }
        if (this._originalMouseUp) {
            button.addEventListener('mouseup', this._originalMouseUp);
        }
        if (this._originalClick) {
            button.addEventListener('click', this._originalClick);
        }
        
        // Ensure minimum touch target size
        ensureTouchTargetSize(button);
    });
    
    // Enhance input controls
    inputs.forEach(input => {
        // Add touch events for range inputs
        if (input.type === 'range') {
            input.addEventListener('touchstart', function(e) {
                e.preventDefault();
                // Haptic feedback for slider interaction
                if (navigator.vibrate) {
                    navigator.vibrate(10);
                }
            }, { passive: false });
            
            input.addEventListener('touchmove', function(e) {
                e.preventDefault();
                // Update value based on touch position
                updateRangeValueFromTouch(this, e);
            }, { passive: false });
        }
        
        // Ensure minimum touch target size
        ensureTouchTargetSize(input);
    });
    
    console.log('Touch enhancements applied successfully');
}

function ensureTouchTargetSize(element) {
    // Ensure minimum touch target size of 44px for mobile
    const rect = element.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    
    if (width < 44 || height < 44) {
        // Add padding to meet minimum touch target size
        const paddingX = Math.max(0, (44 - width) / 2);
        const paddingY = Math.max(0, (44 - height) / 2);
        
        element.style.paddingLeft = (parseFloat(getComputedStyle(element).paddingLeft) + paddingX) + 'px';
        element.style.paddingRight = (parseFloat(getComputedStyle(element).paddingRight) + paddingX) + 'px';
        element.style.paddingTop = (parseFloat(getComputedStyle(element).paddingTop) + paddingY) + 'px';
        element.style.paddingBottom = (parseFloat(getComputedStyle(element).paddingBottom) + paddingY) + 'px';
    }
}

function updateRangeValueFromTouch(rangeElement, touchEvent) {
    const touch = touchEvent.touches[0];
    const rect = rangeElement.getBoundingClientRect();
    const position = (touch.clientX - rect.left) / rect.width;
    const value = rangeElement.min + (position * (rangeElement.max - rangeElement.min));
    
    rangeElement.value = Math.round(value);
    
    // Trigger change event
    const event = new Event('input', { bubbles: true });
    rangeElement.dispatchEvent(event);
    
    // Also trigger change event for immediate updates
    const changeEvent = new Event('change', { bubbles: true });
    rangeElement.dispatchEvent(changeEvent);
}

function ensureViewportMeta() {
    // Check if viewport meta tag exists
    let viewportMeta = document.querySelector('meta[name="viewport"]');
    
    if (!viewportMeta) {
        // Create viewport meta tag
        viewportMeta = document.createElement('meta');
        viewportMeta.name = 'viewport';
        viewportMeta.content = 'width=device-width, initial-scale=1.0, user-scalable=no, maximum-scale=1.0';
        document.head.appendChild(viewportMeta);
        console.log('Added viewport meta tag');
    }
}

// Add CSS for touch feedback
const touchStyles = `
    .touch-active {
        transform: scale(0.95) !important;
        transition: transform 0.1s ease !important;
    }
    
    @media (hover: none) and (pointer: coarse) {
        button, .button_unpressed, .button_pressed, .button_mode, input[type="button"] {
            min-height: 44px !important;
            min-width: 44px !important;
            padding: 12px !important;
        }
        
        input[type="range"] {
            min-height: 44px !important;
            padding: 10px 0 !important;
        }
    }
`;

// Add styles to document
const styleElement = document.createElement('style');
styleElement.textContent = touchStyles;
document.head.appendChild(styleElement);

console.log('Touch enhancements module loaded');