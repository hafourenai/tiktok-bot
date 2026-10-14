import React, { useState } from 'react';
import './WeatherForecast.css';

const weatherEmojis = {
  'Cerah': '☀️',
  'Berawan': '⛅',
  'Cerah Berawan': '🌤️',
  'Hujan': '🌧️',
  'Hujan Lebat': '⛈️',
  'Petir': '⚡',
  'Kabut': '🌫️',
  'Asap': '💨',
};

export const WeatherForecast = ({ forecasts = [], timezone = 'Asia/Jakarta' }) => {
  const [expandedIndex, setExpandedIndex] = useState(null);

  if (!forecasts || forecasts.length === 0) {
    return <div className="forecast-empty">Tidak ada prakiraan tersedia</div>;
  }

  const formatTime = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString('id-ID', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return '--';
    }
  };

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleString('id-ID', {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
      });
    } catch {
      return '--';
    }
  };

  const getTempColor = (temp) => {
    const t = parseInt(temp);
    if (t > 32) return '#d32f2f';
    if (t > 28) return '#f57c00';
    if (t > 24) return '#fbc02d';
    if (t > 20) return '#388e3c';
    return '#1976d2';
  };

  // Group by date
  const groupedByDate = forecasts.reduce((acc, forecast, idx) => {
    const date = formatDate(forecast.utc_datetime);
    if (!acc[date]) acc[date] = [];
    acc[date].push({ ...forecast, originalIndex: idx });
    return acc;
  }, {});

  return (
    <div className="weather-forecast">
      <h2 className="forecast-title">Prakiraan Per Periode</h2>

      <div className="forecast-timeline">
        {Object.entries(groupedByDate).map(([date, dayForecasts]) => (
          <div key={date} className="forecast-day">
            <h3 className="day-header">{date}</h3>

            <div className="forecast-cards">
              {dayForecasts.map((forecast, idx) => {
                const isExpanded = expandedIndex === forecast.originalIndex;
                const emoji = weatherEmojis[forecast.weather_desc] || '🌡️';
                const tempColor = getTempColor(forecast.t);

                return (
                  <div
                    key={forecast.originalIndex}
                    className={`forecast-card ${isExpanded ? 'expanded' : ''}`}
                  >
                    <button
                      className="card-trigger"
                      onClick={() =>
                        setExpandedIndex(isExpanded ? null : forecast.originalIndex)
                      }
                      style={{ '--temp-color': tempColor }}
                    >
                      <div className="card-time">
                        {formatTime(forecast.utc_datetime)}
                      </div>
                      <div className="card-emoji">{emoji}</div>
                      <div className="card-temp">
                        <span className="temp-val">{forecast.t}°</span>
                      </div>
                      <div className="card-desc">{forecast.weather_desc}</div>
                    </button>

                    {isExpanded && (
                      <div className="card-details">
                        <div className="detail-grid">
                          <div className="detail-item">
                            <span className="detail-icon">💧</span>
                            <span className="detail-label">Kelembapan</span>
                            <span className="detail-value">{forecast.hu}%</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-icon">💨</span>
                            <span className="detail-label">Angin</span>
                            <span className="detail-value">{forecast.ws} km/j</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-icon">🧭</span>
                            <span className="detail-label">Arah</span>
                            <span className="detail-value">{forecast.wd}</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-icon">🌊</span>
                            <span className="detail-label">Tinggi Gelombang</span>
                            <span className="detail-value">
                              {forecast.tg || '--'} m
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WeatherForecast;
