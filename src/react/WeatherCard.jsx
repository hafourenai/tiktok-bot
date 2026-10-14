import React, { useState, useEffect } from 'react';
import './WeatherCard.css';

const weatherIcons = {
  'Cerah': '☀️',
  'Berawan': '⛅',
  'Cerah Berawan': '🌤️',
  'Hujan': '🌧️',
  'Hujan Lebat': '⛈️',
  'Petir': '⚡',
  'Kabut': '🌫️',
  'Asap': '💨',
};

export const WeatherCard = ({ data, location }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!data) return <div className="weather-card loading">Loading weather...</div>;

  const {
    weather_desc = 'Cerah',
    t = '--',
    hu = '--',
    ws = '--',
    wd = '--',
    local_datetime = '',
  } = data;

  const icon = weatherIcons[weather_desc] || '🌡️';
  const tempNum = parseInt(t);
  const humidityNum = parseInt(hu);
  const tempColor = tempNum > 30 ? '#ff6b6b' : tempNum > 25 ? '#ffa500' : '#4ecdc4';

  return (
    <div className="weather-card" style={{ '--temp-color': tempColor }}>
      {/* Header */}
      <div className="card-header">
        <div className="location-info">
          <h2 className="location-name">
            {location?.desa}, {location?.kecamatan}
          </h2>
          <p className="location-sub">
            {location?.kotkab}, {location?.provinsi}
          </p>
        </div>
        <button 
          className="expand-btn"
          onClick={() => setExpanded(!expanded)}
          aria-label="Toggle details"
        >
          {expanded ? '✕' : '⊕'}
        </button>
      </div>

      {/* Main Content */}
      <div className="card-main">
        <div className="temp-section">
          <div className="weather-icon">{icon}</div>
          <div className="temp-display">
            <div className="temperature">
              <span className="temp-value">{t}</span>
              <span className="temp-unit">°C</span>
            </div>
            <div className="weather-desc">{weather_desc}</div>
          </div>
        </div>

        {/* Quick Metrics */}
        <div className="metrics-grid">
          <div className="metric-card humidity">
            <span className="metric-icon">💧</span>
            <div className="metric-content">
              <span className="metric-label">Kelembapan</span>
              <span className="metric-value">{hu}%</span>
            </div>
          </div>
          <div className="metric-card wind">
            <span className="metric-icon">💨</span>
            <div className="metric-content">
              <span className="metric-label">Angin</span>
              <span className="metric-value">{ws} km/j</span>
            </div>
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="card-details">
          <div className="detail-row">
            <span className="detail-label">Arah Angin</span>
            <span className="detail-value">{wd}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Waktu Data</span>
            <span className="detail-value">
              {local_datetime ? new Date(local_datetime).toLocaleString('id-ID') : '--'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Zona Waktu</span>
            <span className="detail-value">{location?.timezone || 'Asia/Jakarta'}</span>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="card-footer">
        <p>Prakiraan resmi BMKG Indonesia</p>
      </div>
    </div>
  );
};

export default WeatherCard;
