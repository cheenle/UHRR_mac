import React, { useRef, useEffect } from 'react';
import './SpectrumMobile.css';

const SpectrumMobile = ({ websocketService }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Initialize spectrum display
    const drawSpectrum = () => {
      // Clear canvas
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw grid
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 1;

      // Horizontal lines
      for (let y = 0; y < canvas.height; y += 20) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }

      // Vertical lines
      for (let x = 0; x < canvas.width; x += 20) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }

      // Draw sample spectrum data (placeholder)
      ctx.strokeStyle = '#00ff00';
      ctx.lineWidth = 2;
      ctx.beginPath();

      const centerY = canvas.height / 2;
      for (let x = 0; x < canvas.width; x++) {
        const y = centerY + Math.sin(x * 0.1) * 20 + Math.random() * 10 - 5;
        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }

      ctx.stroke();
    };

    // Initial draw
    drawSpectrum();

    // Update every 100ms
    const interval = setInterval(drawSpectrum, 100);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="spectrum-mobile">
      <canvas
        ref={canvasRef}
        width="300"
        height="80"
        className="spectrum-mobile-canvas"
      />
    </div>
  );
};

export default SpectrumMobile;
