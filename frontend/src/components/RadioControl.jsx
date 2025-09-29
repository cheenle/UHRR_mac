import React, { useState, useEffect } from 'react';
import './RadioControl.css';

const RadioControl = ({ radioService, websocketService }) => {
  const [radioState, setRadioState] = useState({
    frequency: 7050000,
    mode: 'USB',
    power: 100,
    ptt: false,
    signalStrength: 0,
    connected: false
  });

  const [isTransmitting, setIsTransmitting] = useState(false);

  useEffect(() => {
    // Listen for radio state changes
    const handleStatusUpdate = (status) => {
      setRadioState(prevState => ({ ...prevState, ...status }));
    };

    const handlePttChange = (ptt) => {
      setIsTransmitting(ptt);
    };

    radioService.on('statusUpdate', handleStatusUpdate);
    radioService.on('pttChanged', handlePttChange);

    // Request initial status
    radioService.requestStatus();

    return () => {
      radioService.off('statusUpdate', handleStatusUpdate);
      radioService.off('pttChanged', handlePttChange);
    };
  }, [radioService]);

  const handleFrequencyChange = (frequency) => {
    if (radioService.validateFrequency(frequency)) {
      radioService.setFrequency(frequency);
    }
  };

  const handleModeChange = (mode) => {
    if (radioService.validateMode(mode)) {
      radioService.setMode(mode);
    }
  };

  const handlePowerChange = (power) => {
    if (radioService.validatePower(power)) {
      radioService.setPower(power);
    }
  };

  const handlePTTToggle = () => {
    radioService.setPTT(!isTransmitting);
  };

  const formatFrequency = (freq) => {
    return (freq / 1000000).toFixed(3) + ' MHz';
  };

  return (
    <div className="radio-control">
      <div className="radio-control__header">
        <h2>Radio Control</h2>
        <div className={`connection-status ${radioState.connected ? 'connected' : 'disconnected'}`}>
          {radioState.connected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </div>

      <div className="radio-control__main">
        {/* Frequency Control */}
        <div className="control-group">
          <label>Frequency:</label>
          <div className="frequency-display">
            {formatFrequency(radioState.frequency)}
          </div>
          <input
            type="range"
            min="100000"
            max="30000000"
            step="100"
            value={radioState.frequency}
            onChange={(e) => handleFrequencyChange(parseInt(e.target.value))}
            className="frequency-slider"
          />
        </div>

        {/* Mode Selection */}
        <div className="control-group">
          <label>Mode:</label>
          <select
            value={radioState.mode}
            onChange={(e) => handleModeChange(e.target.value)}
            className="mode-selector"
          >
            <option value="USB">USB</option>
            <option value="LSB">LSB</option>
            <option value="CW">CW</option>
            <option value="AM">AM</option>
            <option value="FM">FM</option>
          </select>
        </div>

        {/* Power Control */}
        <div className="control-group">
          <label>Power:</label>
          <input
            type="range"
            min="0"
            max="100"
            value={radioState.power}
            onChange={(e) => handlePowerChange(parseInt(e.target.value))}
            className="power-slider"
          />
          <span className="power-value">{radioState.power}%</span>
        </div>

        {/* Signal Strength */}
        <div className="control-group">
          <label>Signal Strength:</label>
          <div className="signal-meter">
            <div
              className="signal-bar"
              style={{ width: `${radioState.signalStrength}%` }}
            ></div>
          </div>
          <span className="signal-value">S{radioState.signalStrength}</span>
        </div>

        {/* PTT Button */}
        <div className="control-group">
          <button
            className={`ptt-button ${isTransmitting ? 'transmitting' : ''}`}
            onMouseDown={handlePTTToggle}
            onMouseUp={() => radioService.setPTT(false)}
            onMouseLeave={() => radioService.setPTT(false)}
          >
            {isTransmitting ? '🔴 TX' : '⚪ TX'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RadioControl;
