/**
 * Weather API Integration
 * Adapter untuk mengintegrasikan WeatherApp dengan BMKG Python backend
 */

class WeatherAPIClient {
  constructor(baseUrl = 'http://localhost:5000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Fetch prakiraan cuaca untuk lokasi tertentu
   * @param {string} adm4 - Kode administratif level 4 (kelurahan/desa)
   * @returns {Promise<Object>} Data cuaca lengkap
   */
  async getWeatherByLocation(adm4) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/weather?adm4=${adm4}`
      );
      if (!response.ok) throw new Error('Failed to fetch weather data');
      return await response.json();
    } catch (error) {
      console.error('Weather API error:', error);
      throw error;
    }
  }

  /**
   * Fetch prakiraan berdasarkan koordinat GPS
   * @param {number} lat - Latitude
   * @param {number} lon - Longitude
   * @returns {Promise<Object>} Data cuaca lengkap
   */
  async getWeatherByCoordinates(lat, lon) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/weather/coordinates?lat=${lat}&lon=${lon}`
      );
      if (!response.ok) throw new Error('Failed to fetch weather data');
      return await response.json();
    } catch (error) {
      console.error('Weather API error:', error);
      throw error;
    }
  }

  /**
   * Fetch daftar lokasi untuk peta
   * @returns {Promise<Array>} Array lokasi dengan cuaca
   */
  async getAllLocations() {
    try {
      const response = await fetch(`${this.baseUrl}/api/weather/locations`);
      if (!response.ok) throw new Error('Failed to fetch locations');
      return await response.json();
    } catch (error) {
      console.error('Weather API error:', error);
      throw error;
    }
  }

  /**
   * Search lokasi berdasarkan nama
   * @param {string} query - Query pencarian (desa, kecamatan, atau kota)
   * @returns {Promise<Array>} Array hasil pencarian
   */
  async searchLocations(query) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/locations/search?q=${encodeURIComponent(query)}`
      );
      if (!response.ok) throw new Error('Failed to search locations');
      return await response.json();
    } catch (error) {
      console.error('Weather API error:', error);
      throw error;
    }
  }

  /**
   * Generate weather card image (untuk shareable)
   * @param {string} adm4 - Kode administratif
   * @returns {Promise<Blob>} Image binary
   */
  async generateWeatherCard(adm4) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/weather/card?adm4=${adm4}`
      );
      if (!response.ok) throw new Error('Failed to generate card');
      return await response.blob();
    } catch (error) {
      console.error('Weather API error:', error);
      throw error;
    }
  }
}

export default WeatherAPIClient;
