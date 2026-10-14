import React, { useState, useEffect } from 'react';
import { WeatherCard, WeatherMap, WeatherForecast } from './index';
import './WeatherApp.css';

export const WeatherApp = ({ apiBaseUrl = 'https://api.bmkg.go.id' }) => {
  const [currentWeather, setCurrentWeather] = useState(null);
  const [forecasts, setForecasts] = useState([]);
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [view, setView] = useState('card'); // 'card', 'map', 'forecast'

  // Mock data untuk demo
  const mockWeatherData = {
    lokasi: {
      desa: 'Dukuh Baru',
      kecamatan: 'Grogol Petamburan',
      kotkab: 'Jakarta Barat',
      provinsi: 'DKI Jakarta',
      timezone: 'Asia/Jakarta',
      adm4: '3173080',
      lat: -6.1753,
      lon: 106.7949,
    },
    data: [
      {
        lokasi: {
          adm4: '3173080',
          desa: 'Dukuh Baru',
          kecamatan: 'Grogol Petamburan',
        },
        cuaca: [
          [
            {
              utc_datetime: '2026-10-14T09:00:00Z',
              local_datetime: '2026-10-14T16:00:00+07:00',
              t: 28,
              hu: 72,
              ws: 12,
              wd: 'Utara',
              weather_desc: 'Cerah Berawan',
              tg: 0.5,
            },
            {
              utc_datetime: '2026-10-14T12:00:00Z',
              local_datetime: '2026-10-14T19:00:00+07:00',
              t: 26,
              hu: 78,
              ws: 8,
              wd: 'Barat Laut',
              weather_desc: 'Berawan',
              tg: 0.3,
            },
            {
              utc_datetime: '2026-10-14T15:00:00Z',
              local_datetime: '2026-10-14T22:00:00+07:00',
              t: 24,
              hu: 85,
              ws: 6,
              wd: 'Barat',
              weather_desc: 'Berawan',
              tg: 0.2,
            },
          ],
        ],
      },
    ],
  };

  const mockLocations = [
    {
      desa: 'Dukuh Baru',
      kecamatan: 'Grogol Petamburan',
      kotkab: 'Jakarta Barat',
      provinsi: 'DKI Jakarta',
      lat: -6.1753,
      lon: 106.7949,
      temp: 28,
      hu: 72,
      ws: 12,
      wd: 'Utara',
      weather_desc: 'Cerah Berawan',
    },
    {
      desa: 'Kebon Besar',
      kecamatan: 'Kemang',
      kotkab: 'Jakarta Selatan',
      provinsi: 'DKI Jakarta',
      lat: -6.2662,
      lon: 106.8154,
      temp: 30,
      hu: 68,
      ws: 10,
      wd: 'Timur Laut',
      weather_desc: 'Cerah',
    },
    {
      desa: 'Cibinong',
      kecamatan: 'Cibinong',
      kotkab: 'Bogor',
      provinsi: 'Jawa Barat',
      lat: -6.4667,
      lon: 106.8333,
      temp: 25,
      hu: 80,
      ws: 5,
      wd: 'Selatan',
      weather_desc: 'Hujan Ringan',
    },
  ];

  // Load data on mount
  useEffect(() => {
    loadWeatherData();
  }, []);

  const loadWeatherData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Simulasi fetch dari API
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const currentData = mockWeatherData.data[0].cuaca[0][0];
      const locationData = mockWeatherData.lokasi;

      setCurrentWeather({
        ...currentData,
        ...locationData,
      });

      setSelectedLocation(locationData);

      const allForecasts = mockWeatherData.data[0].cuaca[0];
      setForecasts(allForecasts);

      setLocations(mockLocations);
    } catch (err) {
      setError('Gagal memuat data cuaca');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLocationSelect = (location) => {
    setSelectedLocation(location);
    // Di implementasi nyata, fetch data untuk lokasi ini
    const mockData = mockLocations.find(
      (l) => l.desa === location.desa && l.kecamatan === location.kecamatan
    );
    if (mockData) {
      setCurrentWeather({
        ...mockData,
        weather_desc: mockData.weather_desc,
        t: mockData.temp,
        hu: mockData.hu,
        ws: mockData.ws,
        wd: mockData.wd,
      });
    }
  };

  return (
    <div className="weather-app">
      {/* Header */}
      <header className="app-header">
        <h1>Prakiraan Cuaca Indonesia</h1>
        <p>Data resmi BMKG • Diperbarui secara real-time</p>
      </header>

      {/* View Tabs */}
      <div className="view-tabs">
        <button
          className={`tab ${view === 'card' ? 'active' : ''}`}
          onClick={() => setView('card')}
        >
          Kartu Cuaca
        </button>
        <button
          className={`tab ${view === 'map' ? 'active' : ''}`}
          onClick={() => setView('map')}
        >
          Peta Penyebaran
        </button>
        <button
          className={`tab ${view === 'forecast' ? 'active' : ''}`}
          onClick={() => setView('forecast')}
        >
          Prakiraan Periode
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={loadWeatherData}>Coba Lagi</button>
        </div>
      )}

      {/* Loading State */}
      {loading && <div className="loading-spinner">Memuat data...</div>}

      {/* Content */}
      {!loading && (
        <div className="app-content">
          {view === 'card' && currentWeather && (
            <div className="view-container">
              <WeatherCard data={currentWeather} location={selectedLocation} />
              <aside className="sidebar">
                <h3>Lokasi Terdekat</h3>
                <div className="location-list">
                  {locations.map((loc, idx) => (
                    <button
                      key={idx}
                      className={`location-item ${
                        selectedLocation?.desa === loc.desa ? 'active' : ''
                      }`}
                      onClick={() => handleLocationSelect(loc)}
                    >
                      <div className="location-name">{loc.desa}</div>
                      <div className="location-meta">
                        {loc.kotkab} • {loc.temp}°C
                      </div>
                    </button>
                  ))}
                </div>
              </aside>
            </div>
          )}

          {view === 'map' && (
            <div className="view-container full">
              <WeatherMap data={mockWeatherData} locations={locations} />
            </div>
          )}

          {view === 'forecast' && (
            <div className="view-container full">
              <WeatherForecast
                forecasts={forecasts}
                timezone={selectedLocation?.timezone}
              />
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <footer className="app-footer">
        <p>
          © 2026 Badan Meteorologi Klimatologi dan Geofisika (BMKG) •
          <a href="https://data.bmkg.go.id" target="_blank" rel="noopener noreferrer">
            {' '}
            data.bmkg.go.id
          </a>
        </p>
      </footer>
    </div>
  );
};

export default WeatherApp;
