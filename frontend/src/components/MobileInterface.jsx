import React, { useState, useEffect } from 'react';
import SpectrumMobile from './SpectrumMobile';
import './MobileInterface.css';

const MobileInterface = ({ radioService, audioService, websocketService }) => {
  const [radioState, setRadioState] = useState({
    frequency: 7050000,
    mode: 'USB',
    power: 100,
    ptt: false,
    signalStrength: 0,
    connected: false
  });

  const [currentTime, setCurrentTime] = useState(new Date());
  const [isTransmitting, setIsTransmitting] = useState(false);
  const [showFrequencyInput, setShowFrequencyInput] = useState(false);
  const [frequencyInput, setFrequencyInput] = useState('');

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleStatusUpdate = (status) => {
      setRadioState(prevState => ({ ...prevState, ...status }));
    };

    const handlePttChange = (ptt) => {
      setIsTransmitting(ptt);
    };

    radioService.on('statusUpdate', handleStatusUpdate);
    radioService.on('pttChanged', handlePttChange);

    radioService.requestStatus();

    return () => {
      radioService.off('statusUpdate', handleStatusUpdate);
      radioService.off('pttChanged', handlePttChange);
    };
  }, [radioService]);

  const formatFrequency = (freq) => {
    return (freq / 1000000).toFixed(3);
  };

  const formatFrequencyFull = (freq) => {
    return freq.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  };

  const handleFrequencyClick = () => {
    setShowFrequencyInput(true);
    setFrequencyInput(radioState.frequency.toString());
  };

  const handleFrequencySubmit = () => {
    const freq = parseInt(frequencyInput.replace(/\./g, ''));
    if (radioService.validateFrequency(freq)) {
      radioService.setFrequency(freq);
      setShowFrequencyInput(false);
    }
  };

  const handleFrequencyKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleFrequencySubmit();
    }
  };

  const handleModeChange = (mode) => {
    radioService.setMode(mode);
  };

  const handlePTTToggle = () => {
    radioService.setPTT(!isTransmitting);
  };

  const handleStepChange = (step) => {
    // Implement frequency step change
    const currentFreq = radioState.frequency;
    const newFreq = step > 0 ? currentFreq + 100 : currentFreq - 100; // 100Hz steps
    if (radioService.validateFrequency(newFreq)) {
      radioService.setFrequency(newFreq);
    }
  };

  return (
    <div className="mobile-interface">
      {/* Header */}
      <div className="mobile-header">
        <div className="time-display">
          {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
        <div className="connection-status">
          <div className={`signal-bars ${radioState.connected ? 'connected' : 'disconnected'}`}>
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
            <div className="bar"></div>
          </div>
        </div>
        <button className="disconnect-btn">Disconnect</button>
      </div>

      {/* Main Display */}
      <div className="main-display">
        {/* Frequency Display */}
        <div className="frequency-display" onClick={handleFrequencyClick}>
          {showFrequencyInput ? (
            <input
              type="text"
              value={frequencyInput}
              onChange={(e) => setFrequencyInput(e.target.value)}
              onBlur={handleFrequencySubmit}
              onKeyPress={handleFrequencyKeyPress}
              className="frequency-input"
              autoFocus
            />
          ) : (
            <>
              <div className="frequency-main">{formatFrequency(radioState.frequency)} MHz</div>
              <div className="frequency-full">{formatFrequencyFull(radioState.frequency)}</div>
            </>
          )}
        </div>

        {/* Mode Selection */}
        <div className="mode-selection">
          <button
            className={`mode-btn ${radioState.mode === 'LSB' ? 'active' : ''}`}
            onClick={() => handleModeChange('LSB')}
          >
            LSB
          </button>
          <button
            className={`mode-btn ${radioState.mode === 'USB' ? 'active' : ''}`}
            onClick={() => handleModeChange('USB')}
          >
            USB
          </button>
          <button
            className={`mode-btn ${radioState.mode === 'CW' ? 'active' : ''}`}
            onClick={() => handleModeChange('CW')}
          >
            CW
          </button>
          <button
            className={`mode-btn ${radioState.mode === 'AM' ? 'active' : ''}`}
            onClick={() => handleModeChange('AM')}
          >
            AM
          </button>
          <button
            className={`mode-btn ${radioState.mode === 'FM' ? 'active' : ''}`}
            onClick={() => handleModeChange('FM')}
          >
            FM
          </button>
        </div>

        {/* Control Buttons */}
        <div className="control-buttons">
          <button className="control-btn">Tune</button>
          <button className="control-btn">Mic</button>
          <button className="control-btn">VOX</button>
          <button className="control-btn">Main</button>
          <button className="control-btn">160m</button>
        </div>

        {/* Signal Strength */}
        <div className="signal-strength">
          <div className="signal-label">Level</div>
          <div className="signal-meter">
            <div
              className="signal-fill"
              style={{ width: `${radioState.signalStrength * 10}%` }}
            ></div>
          </div>
          <div className="signal-value">{radioState.signalStrength}</div>
        </div>

        {/* Meters */}
        <div className="meters">
          <div className="meter">
            <div className="meter-label">SWR</div>
            <div className="meter-bar">
              <div className="meter-fill swr" style={{ width: '60%' }}></div>
            </div>
          </div>
          <div className="meter">
            <div className="meter-label">Mic Level</div>
            <div className="meter-bar">
              <div className="meter-fill mic" style={{ width: '75%' }}></div>
            </div>
            <div className="meter-value">100.0%</div>
          </div>
        </div>

        {/* Bottom Controls */}
        <div className="bottom-controls">
          <button className="log-btn">Log</button>
          <div className="ptt-area">
            <button
              className={`ptt-btn ${isTransmitting ? 'transmitting' : ''}`}
              onTouchStart={handlePTTToggle}
              onTouchEnd={() => radioService.setPTT(false)}
            >
              {isTransmitting ? '🔴 PTT' : '⚪ PTT'}
            </button>
          </div>
          <div className="step-controls">
            <button className="step-btn" onClick={() => handleStepChange(-1)}>‹‹</button>
            <button className="step-btn" onClick={() => handleStepChange(-1)}>‹</button>
            <span className="step-value">Step 10</span>
            <button className="step-btn" onClick={() => handleStepChange(1)}>›</button>
            <button className="step-btn" onClick={() => handleStepChange(1)}>››</button>
          </div>
        </div>

        {/* Spectrum Display */}
        <div className="spectrum-area">
          <SpectrumMobile websocketService={websocketService} />
        </div>

        {/* Bottom Navigation */}
        <div className="bottom-nav">
          <button className="nav-btn active">VFO</button>
          <button className="nav-btn">Modes</button>
          <button className="nav-btn">Tools</button>
          <button className="nav-btn">IC-7610</button>
          <button className="nav-btn">Settings</button>
        </div>
      </div>
    </div>
  );
};

export default MobileInterface;
