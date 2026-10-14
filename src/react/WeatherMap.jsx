import React, { useState, useEffect, useRef } from 'react';
import './WeatherMap.css';

export const WeatherMap = ({ data, locations = [] }) => {
  const mapRef = useRef(null);
  const [map, setMap] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [zoom, setZoom] = useState(5);
  const [showLegend, setShowLegend] = useState(true);

  // Inisialisasi peta dengan Leaflet
  useEffect(() => {
    if (!mapRef.current) return;

    // Lazy load Leaflet
    const loadLeaflet = async () => {
      if (window.L) {
        initializeMap();
      } else {
        // Fallback: gunakan canvas-based visualization
        renderCanvasMap();
      }
    };

    loadLeaflet();

    return () => {
      if (map) map.remove();
    };
  }, []);

  const initializeMap = () => {
    if (!window.L) return;

    const leafletMap = window.L.map(mapRef.current).setView([-2.548, 118.0894], 5);

    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(leafletMap);

    setMap(leafletMap);
    addMarkers(leafletMap);
  };

  const renderCanvasMap = () => {
    // Fallback canvas-based visualization jika Leaflet tidak tersedia
    const canvas = document.createElement('canvas');
    canvas.width = mapRef.current.clientWidth;
    canvas.height = mapRef.current.clientHeight;
    mapRef.current.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    drawMapBackground(ctx, canvas.width, canvas.height);
  };

  const drawMapBackground = (ctx, width, height) => {
    // Gradient background untuk Indonesia
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, '#e3f2fd');
    gradient.addColorStop(1, '#bbdefb');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    // Grid
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const x = (width / 10) * i;
      const y = (height / 10) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }
  };

  const addMarkers = (leafletMap) => {
    const newMarkers = locations.map((loc) => {
      const tempNum = parseInt(loc.temp);
      const color = getTempColor(tempNum);

      const marker = window.L.circleMarker(
        [loc.lat, loc.lon],
        {
          radius: 20,
          fillColor: color,
          color: '#fff',
          weight: 3,
          opacity: 0.9,
          fillOpacity: 0.8,
        }
      )
        .bindPopup(
          `<div class="popup-content">
            <strong>${loc.desa}, ${loc.kecamatan}</strong>
            <p>${loc.weather_desc}</p>
            <p>${loc.temp}°C</p>
          </div>`
        )
        .on('click', () => setSelectedLocation(loc))
        .addTo(leafletMap);

      return marker;
    });

    setMarkers(newMarkers);
  };

  const getTempColor = (temp) => {
    if (temp > 32) return '#d32f2f'; // Merah terang
    if (temp > 28) return '#f57c00'; // Oranye
    if (temp > 24) return '#fbc02d'; // Kuning
    if (temp > 20) return '#388e3c'; // Hijau
    return '#1976d2'; // Biru
  };

  const handleZoom = (delta) => {
    const newZoom = Math.max(3, Math.min(18, zoom + delta));
    setZoom(newZoom);
    if (map) map.setZoom(newZoom);
  };

  return (
    <div className="weather-map-container">
      {/* Controls */}
      <div className="map-controls">
        <button
          className="control-btn zoom-in"
          onClick={() => handleZoom(1)}
          title="Perbesar"
        >
          +
        </button>
        <button
          className="control-btn zoom-out"
          onClick={() => handleZoom(-1)}
          title="Perkecil"
        >
          −
        </button>
        <button
          className="control-btn legend-toggle"
          onClick={() => setShowLegend(!showLegend)}
          title="Legenda"
        >
          ℹ
        </button>
      </div>

      {/* Peta */}
      <div ref={mapRef} className="map-canvas" />

      {/* Legenda */}
      {showLegend && (
        <div className="map-legend">
          <h3>Legenda Suhu</h3>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#d32f2f' }} />
            <span>&gt; 32°C</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#f57c00' }} />
            <span>28 - 32°C</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#fbc02d' }} />
            <span>24 - 28°C</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#388e3c' }} />
            <span>20 - 24°C</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ backgroundColor: '#1976d2' }} />
            <span>&lt; 20°C</span>
          </div>
        </div>
      )}

      {/* Info Panel */}
      {selectedLocation && (
        <div className="map-info-panel">
          <button
            className="close-btn"
            onClick={() => setSelectedLocation(null)}
          >
            ✕
          </button>
          <h4>{selectedLocation.desa}</h4>
          <div className="info-row">
            <span>Kondisi</span>
            <strong>{selectedLocation.weather_desc}</strong>
          </div>
          <div className="info-row">
            <span>Suhu</span>
            <strong>{selectedLocation.temp}°C</strong>
          </div>
          <div className="info-row">
            <span>Kelembapan</span>
            <strong>{selectedLocation.hu}%</strong>
          </div>
          <div className="info-row">
            <span>Angin</span>
            <strong>{selectedLocation.ws} km/j</strong>
          </div>
        </div>
      )}
    </div>
  );
};

export default WeatherMap;
