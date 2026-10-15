import { useState, useEffect } from "preact/hooks";
import { getWeatherByCoordinates, getWeatherByCode, searchLocations } from "src/services/bmkg-api";
import type { WeatherData, LocationInfo } from "src/services/bmkg-api";
import { Search, MapPin, Cloud, Droplets, Wind } from "lucide-preact";
import "./WeatherStyles.css";

export default function WeatherViewer() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<LocationInfo[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Handle search input
  const handleSearch = async (value: string) => {
    setSearchQuery(value);
    if (value.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    try {
      const results = await searchLocations(value);
      setSuggestions(results);
      setShowSuggestions(true);
    } catch (err) {
      console.error("Search error:", err);
    }
  };

  // Handle location selection
  const handleSelectLocation = async (code: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWeatherByCode(code);
      setWeather(data);
      setSuggestions([]);
      setShowSuggestions(false);
    } catch (err) {
      setError("Failed to fetch weather data");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Get weather by GPS
  const handleGPS = () => {
    if (!navigator.geolocation) {
      setError("Geolocation not supported");
      return;
    }

    setLoading(true);
    setError(null);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const data = await getWeatherByCoordinates(
            position.coords.latitude,
            position.coords.longitude,
          );
          setWeather(data);
        } catch (err) {
          setError("Failed to fetch weather for your location");
          console.error(err);
        } finally {
          setLoading(false);
        }
      },
      () => {
        setError("Unable to get your location");
        setLoading(false);
      },
    );
  };

  return (
    <div className="weather-container">
      <div className="weather-header">
        <h2>Weather Forecast (BMKG)</h2>
        <p>Get Indonesian weather predictions from official BMKG data</p>
      </div>

      {/* Search Section */}
      <div className="weather-search">
        <div className="search-input-wrapper">
          <Search size={20} />
          <input
            type="text"
            placeholder="Search location..."
            value={searchQuery}
            onChange={(e) => handleSearch((e.target as HTMLInputElement).value)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            disabled={loading}
          />
        </div>

        {showSuggestions && suggestions.length > 0 && (
          <div className="suggestions">
            {suggestions.map((location) => (
              <div
                key={location.code}
                className="suggestion-item"
                onClick={() => handleSelectLocation(location.code)}
              >
                {location.name}
              </div>
            ))}
          </div>
        )}

        <button
          className="gps-button"
          onClick={handleGPS}
          disabled={loading}
          title="Use GPS to get weather for your location"
        >
          <MapPin size={18} />
          Current Location
        </button>
      </div>

      {/* Error Message */}
      {error && <div className="error-message">{error}</div>}

      {/* Loading State */}
      {loading && <div className="loading">Loading weather data...</div>}

      {/* Weather Display */}
      {weather && !loading && (
        <div className="weather-display">
          {/* Location Info */}
          <div className="location-info">
            <h3>
              {weather.lokasi.desa}, {weather.lokasi.kecamatan}
            </h3>
            <p>
              {weather.lokasi.kotkab}, {weather.lokasi.provinsi}
            </p>
          </div>

          {/* Current Weather Card */}
          {weather.data[0]?.cuaca[0]?.[0] && (
            <div className="weather-card current">
              <div className="card-header">Current Forecast</div>
              <div className="card-content">
                <div className="weather-main">
                  <Cloud size={64} className="weather-icon" />
                  <div className="weather-info">
                    <div className="temperature">
                      {weather.data[0].cuaca[0][0].t
                        ? Math.round(weather.data[0].cuaca[0][0].t)
                        : "--"}
                      °C
                    </div>
                    <div className="condition">
                      {weather.data[0].cuaca[0][0].weather_desc}
                    </div>
                  </div>
                </div>

                <div className="weather-details">
                  <div className="detail">
                    <Droplets size={18} />
                    <span>
                      Humidity: {weather.data[0].cuaca[0][0].hu || "--"}%
                    </span>
                  </div>
                  <div className="detail">
                    <Wind size={18} />
                    <span>Wind: {weather.data[0].cuaca[0][0].ws || "--"} km/h</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Forecast Timeline */}
          {weather.data[0]?.cuaca && (
            <div className="forecast-timeline">
              <div className="timeline-header">Next Hours</div>
              <div className="timeline-scroll">
                {weather.data[0].cuaca[0]?.slice(0, 8).map((forecast, idx) => {
                  const dt = new Date(forecast.utc_datetime);
                  const time = dt.toLocaleTimeString("id-ID", {
                    hour: "2-digit",
                    minute: "2-digit",
                  });
                  return (
                    <div key={idx} className="timeline-item">
                      <div className="time">{time}</div>
                      <div className="icon">
                        <Cloud size={32} />
                      </div>
                      <div className="temp">{forecast.t ? Math.round(forecast.t) : "--"}°</div>
                      <div className="desc">{forecast.weather_desc.substring(0, 12)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!weather && !loading && !error && (
        <div className="empty-state">
          <Cloud size={64} />
          <p>Search for a location or use GPS to view weather forecast</p>
        </div>
      )}
    </div>
  );
}
