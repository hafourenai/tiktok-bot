/**
 * BMKG Weather API Service
 * Fetches weather forecast data from Indonesian Meteorological, Climatological and Geophysical Agency
 */

export interface WeatherLocation {
  adm4: string;
  provinsi: string;
  kotkab: string;
  kecamatan: string;
  desa: string;
  timezone: string;
}

export interface WeatherData {
  lokasi: WeatherLocation;
  data: Array<{
    lokasi: WeatherLocation;
    cuaca: Array<Array<{
      utc_datetime: string;
      analysis_date: string;
      weather_desc: string;
      t: number | null;
      hu: number | null;
      ws: number | null;
      wd: string;
    }>>;
  }>;
}

export interface LocationInfo {
  code: string;
  name: string;
}

const BMKG_BASE_URL = "https://data.bmkg.go.id/api";
const NOMINATIM_URL = "https://nominatim.openstreetmap.org";
// Keep wilayah.id requests same-origin. The upstream API does not allow
// browser cross-origin requests, so Vercel (and Vite in development) proxy it.
const WILAYAH_API = "/api/wilayah";

/**
 * Get weather data by coordinates (latitude, longitude)
 */
export async function getWeatherByCoordinates(
  lat: number,
  lon: number,
): Promise<WeatherData> {
  try {
    // First, reverse geocode to get location info
    const geoResponse = await fetch(
      `${NOMINATIM_URL}/reverse?format=json&lat=${lat}&lon=${lon}`,
    );
    if (!geoResponse.ok) throw new Error("Geocoding failed");

    const geoData = await geoResponse.json();
    const admin = geoData.address || {};

    // Try to match with BMKG coordinates
    const provinceCode = await getProvinceCode(admin.state || "");
    if (!provinceCode) throw new Error("Province not found");

    const regencyCode = await getRegencyCode(provinceCode, admin.county || "");
    if (!regencyCode) throw new Error("Regency not found");

    const districtCode = await getDistrictCode(regencyCode, admin.suburb || "");
    if (!districtCode) throw new Error("District not found");

    const villageCode = await getVillageCode(districtCode, admin.neighbourhood || "");
    if (!villageCode) throw new Error("Village not found");

    // Fetch weather data for this location
    return await getWeatherByCode(villageCode);
  } catch (error) {
    throw new Error(`Failed to get weather by coordinates: ${error}`);
  }
}

/**
 * Get weather data by location code (ADM4)
 */
export async function getWeatherByCode(code: string): Promise<WeatherData> {
  try {
    const response = await fetch(
      `${BMKG_BASE_URL}/publik/prakiraan-cuaca?adm4=${code}`,
    );
    if (!response.ok) throw new Error("Weather data not found");

    const data = await response.json();
    return data as WeatherData;
  } catch (error) {
    throw new Error(`Failed to get weather: ${error}`);
  }
}

/**
 * Search locations by name
 */
export async function searchLocations(query: string): Promise<LocationInfo[]> {
  try {
    // Search provinces first
    const response = await fetch(`${WILAYAH_API}/provinces.json`);
    if (!response.ok) throw new Error("Location search failed");

    const data = await response.json();
    const provinces = data.data || [];

    return provinces
      .filter((p: any) => p.name.toLowerCase().includes(query.toLowerCase()))
      .map((p: any) => ({
        code: p.code,
        name: p.name,
      }))
      .slice(0, 10); // Limit to 10 results
  } catch (error) {
    throw new Error(`Failed to search locations: ${error}`);
  }
}

/**
 * Helper: Get province code by name
 */
async function getProvinceCode(name: string): Promise<string | null> {
  try {
    const response = await fetch(`${WILAYAH_API}/provinces.json`);
    const data = await response.json();
    const province = (data.data || []).find(
      (p: any) => p.name.toLowerCase() === name.toLowerCase(),
    );
    return province?.code || null;
  } catch {
    return null;
  }
}

/**
 * Helper: Get regency code by province and name
 */
async function getRegencyCode(provinceCode: string, name: string): Promise<string | null> {
  try {
    const response = await fetch(`${WILAYAH_API}/regencies/${provinceCode}.json`);
    const data = await response.json();
    const regency = (data.data || []).find(
      (r: any) => r.name.toLowerCase() === name.toLowerCase(),
    );
    return regency?.code || null;
  } catch {
    return null;
  }
}

/**
 * Helper: Get district code by regency and name
 */
async function getDistrictCode(regencyCode: string, name: string): Promise<string | null> {
  try {
    const response = await fetch(`${WILAYAH_API}/districts/${regencyCode}.json`);
    const data = await response.json();
    const district = (data.data || []).find(
      (d: any) => d.name.toLowerCase() === name.toLowerCase(),
    );
    return district?.code || null;
  } catch {
    return null;
  }
}

/**
 * Helper: Get village code by district and name
 */
async function getVillageCode(districtCode: string, name: string): Promise<string | null> {
  try {
    const response = await fetch(`${WILAYAH_API}/villages/${districtCode}.json`);
    const data = await response.json();
    const village = (data.data || []).find(
      (v: any) => v.name.toLowerCase() === name.toLowerCase(),
    );
    return village?.code || null;
  } catch {
    return null;
  }
}
