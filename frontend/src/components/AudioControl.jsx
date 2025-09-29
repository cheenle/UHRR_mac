import React, { useState, useEffect } from 'react';
import './AudioControl.css';

const AudioControl = ({ audioService, websocketService }) => {
  const [audioStats, setAudioStats] = useState({
    isRecording: false,
    bufferLength: 0,
    sampleRate: 24000,
    sequenceNumber: 0
  });

  const [micGain, setMicGain] = useState(50);
  const [speakerVolume, setSpeakerVolume] = useState(70);

  useEffect(() => {
    const interval = setInterval(() => {
      if (audioService) {
        setAudioStats(audioService.getAudioStats());
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [audioService]);

  const handleStartTransmission = async () => {
    try {
      await audioService.startTransmission();
    } catch (error) {
      console.error('Failed to start transmission:', error);
    }
  };

  const handleStopTransmission = () => {
    audioService.stopTransmission();
  };

  const handleMicGainChange = (value) => {
    setMicGain(value);
    // Send gain change to backend
    websocketService.send('audio-gain', { type: 'mic', value: value / 100 });
  };

  const handleSpeakerVolumeChange = (value) => {
    setSpeakerVolume(value);
    // Send volume change to backend
    websocketService.send('audio-gain', { type: 'speaker', value: value / 100 });
  };

  return (
    <div className="audio-control">
      <div className="audio-control__header">
        <h3>Audio Control</h3>
        <div className="audio-status">
          <span className={`status-indicator ${audioStats.isRecording ? 'recording' : 'idle'}`}>
            {audioStats.isRecording ? '🔴 Recording' : '⚪ Idle'}
          </span>
        </div>
      </div>

      <div className="audio-control__main">
        {/* Transmission Controls */}
        <div className="control-section">
          <h4>Transmission</h4>
          <div className="transmission-controls">
            <button
              className={`tx-button ${audioStats.isRecording ? 'active' : ''}`}
              onMouseDown={handleStartTransmission}
              onMouseUp={handleStopTransmission}
              onMouseLeave={handleStopTransmission}
            >
              {audioStats.isRecording ? '🔴 TX ON' : '⚪ TX OFF'}
            </button>
          </div>
        </div>

        {/* Gain Controls */}
        <div className="control-section">
          <h4>Audio Levels</h4>

          <div className="gain-control">
            <label>Microphone Gain:</label>
            <input
              type="range"
              min="0"
              max="200"
              value={micGain}
              onChange={(e) => handleMicGainChange(parseInt(e.target.value))}
              className="gain-slider"
            />
            <span className="gain-value">{micGain}%</span>
          </div>

          <div className="gain-control">
            <label>Speaker Volume:</label>
            <input
              type="range"
              min="0"
              max="100"
              value={speakerVolume}
              onChange={(e) => handleSpeakerVolumeChange(parseInt(e.target.value))}
              className="volume-slider"
            />
            <span className="volume-value">{speakerVolume}%</span>
          </div>
        </div>

        {/* Audio Statistics */}
        <div className="control-section">
          <h4>Audio Statistics</h4>
          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-label">Sample Rate:</span>
              <span className="stat-value">{audioStats.sampleRate} Hz</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Buffer Length:</span>
              <span className="stat-value">{audioStats.bufferLength} frames</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Sequence:</span>
              <span className="stat-value">{audioStats.sequenceNumber}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Status:</span>
              <span className={`stat-value ${audioStats.isRecording ? 'recording' : 'idle'}`}>
                {audioStats.isRecording ? 'Recording' : 'Idle'}
              </span>
            </div>
          </div>
        </div>

        {/* Audio Quality Settings */}
        <div className="control-section">
          <h4>Audio Quality</h4>
          <div className="quality-controls">
            <div className="quality-item">
              <label>Echo Cancellation:</label>
              <input type="checkbox" defaultChecked={false} />
            </div>
            <div className="quality-item">
              <label>Noise Suppression:</label>
              <input type="checkbox" defaultChecked={false} />
            </div>
            <div className="quality-item">
              <label>Auto Gain Control:</label>
              <input type="checkbox" defaultChecked={true} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AudioControl;
