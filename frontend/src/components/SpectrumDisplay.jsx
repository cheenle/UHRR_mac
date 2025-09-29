import React, { useRef, useEffect, useState } from 'react';
import './SpectrumDisplay.css';

const SpectrumDisplay = ({ websocketService }) => {
  const canvasRef = useRef(null);
  const [spectrumData, setSpectrumData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Listen for spectrum data
    const handleSpectrumData = (data) => {
      setSpectrumData(data);
    };

    const handleConnected = () => {
      setIsConnected(true);
    };

    const handleDisconnected = () => {
      setIsConnected(false);
      setSpectrumData(null);
    };

    websocketService.on('spectrumData', handleSpectrumData);
    websocketService.on('connected', handleConnected);
    websocketService.on('disconnected', handleDisconnected);

    return () => {
      websocketService.off('spectrumData', handleSpectrumData);
      websocketService.off('connected', handleConnected);
      websocketService.off('disconnected', handleDisconnected);
    };
  }, [websocketService]);

  useEffect(() => {
    if (spectrumData && canvasRef.current) {
      drawSpectrum();
    }
  }, [spectrumData]);

  const drawSpectrum = () => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const { fftData, sampleRate, centerFreq } = spectrumData;

    if (!fftData || fftData.length === 0) return;

    // Clear canvas
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw spectrum
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 1;
    ctx.beginPath();

    const binWidth = canvas.width / fftData.length;

    for (let i = 0; i < fftData.length; i++) {
      const amplitude = fftData[i];
      const x = i * binWidth;
      const y = canvas.height - (amplitude / 255) * canvas.height;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();

    // Draw frequency markers
    drawFrequencyMarkers(ctx, canvas.width, canvas.height, centerFreq, sampleRate);
  };

  const drawFrequencyMarkers = (ctx, width, height, centerFreq, sampleRate) => {
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px monospace';

    const bandwidth = sampleRate / 2;
    const freqStep = bandwidth / 4; // 4 markers on each side

    for (let i = -2; i <= 2; i++) {
      const freq = centerFreq + (i * freqStep);
      const x = (width / 2) + (i * (width / 4));

      // Draw vertical line
      ctx.strokeStyle = '#666';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Draw frequency label
      ctx.fillStyle = '#ffffff';
      ctx.fillText(`${(freq / 1000000).toFixed(1)}M`, x - 20, height - 5);
    }
  };

  return (
    <div className="spectrum-display">
      <div className="spectrum-display__header">
        <h3>Real-time Spectrum</h3>
        <div className={`connection-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '🟢 Live' : '🔴 Offline'}
        </div>
      </div>

      <div className="spectrum-display__canvas-container">
        <canvas
          ref={canvasRef}
          width="800"
          height="300"
          className="spectrum-canvas"
        />
      </div>

      {spectrumData && (
        <div className="spectrum-display__info">
          <div className="info-item">
            <span>Center: </span>
            <span>{(spectrumData.centerFreq / 1000000).toFixed(3)} MHz</span>
          </div>
          <div className="info-item">
            <span>Bandwidth: </span>
            <span>{(spectrumData.sampleRate / 1000).toFixed(0)} kHz</span>
          </div>
          <div className="info-item">
            <span>FFT Size: </span>
            <span>{spectrumData.fftSize || 'Unknown'}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default SpectrumDisplay;
