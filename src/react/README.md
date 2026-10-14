# React Weather Components

Komponen React untuk tampilan cuaca Indonesia yang modern dan interaktif.

## Komponen

### 1. WeatherCard
Kartu cuaca utama dengan informasi real-time:
- Display suhu besar dengan ikon cuaca animasi
- Metrik cepat (kelembapan, kecepatan angin)
- Detail tambahan (arah angin, zona waktu) yang dapat diperluas
- Glassmorphism design dengan gradien responsif

```jsx
import { WeatherCard } from '@/react';

<WeatherCard 
  data={{
    weather_desc: 'Cerah Berawan',
    t: 28,
    hu: 72,
    ws: 12,
    wd: 'Utara',
    local_datetime: '2026-10-14T16:00:00+07:00'
  }}
  location={{
    desa: 'Dukuh Baru',
    kecamatan: 'Grogol Petamburan',
    kotkab: 'Jakarta Barat',
    provinsi: 'DKI Jakarta',
    timezone: 'Asia/Jakarta'
  }}
/>
```

### 2. WeatherMap
Peta interaktif penyebaran cuaca:
- Integrasi Leaflet (atau canvas fallback)
- Marker berwarna berdasarkan suhu
- Legenda suhu interaktif
- Info panel untuk lokasi yang dipilih
- Zoom controls

```jsx
import { WeatherMap } from '@/react';

<WeatherMap 
  locations={[
    {
      desa: 'Dukuh Baru',
      lat: -6.1753,
      lon: 106.7949,
      temp: 28,
      weather_desc: 'Cerah Berawan',
      hu: 72,
      ws: 12
    }
  ]}
/>
```

### 3. WeatherForecast
Timeline prakiraan cuaca per periode:
- Dikelompokkan per hari
- Expandable cards untuk detail tambahan
- Emoji cuaca animasi
- Warna suhu responsif

```jsx
import { WeatherForecast } from '@/react';

<WeatherForecast 
  forecasts={[
    {
      utc_datetime: '2026-10-14T09:00:00Z',
      weather_desc: 'Cerah Berawan',
      t: 28,
      hu: 72,
      ws: 12,
      wd: 'Utara'
    }
  ]}
  timezone="Asia/Jakarta"
/>
```

### 4. WeatherApp
Aplikasi lengkap dengan semua fitur:
- Tab switching (Kartu, Peta, Prakiraan)
- Sidebar lokasi terdekat
- Error & loading states
- Mock data untuk development

```jsx
import { WeatherApp } from '@/react';

<WeatherApp apiBaseUrl="https://api.bmkg.go.id" />
```

## Fitur

✅ **UI Modern**
- Glassmorphism design
- Gradient backgrounds
- Smooth animations
- Dark mode ready

✅ **Responsif**
- Desktop, tablet, mobile
- Touch-friendly controls
- Optimized layouts

✅ **Interaktif**
- Expandable details
- Location selection
- Map markers
- Forecast timeline

✅ **Accessible**
- Semantic HTML
- ARIA labels
- Keyboard navigation
- High contrast

## Dependencies

```json
{
  "react": "^18.0",
  "leaflet": "^1.9.0"  // Optional, untuk peta interaktif
}
```

## Setup

```bash
# Install dependencies
npm install

# Development
npm run dev

# Build
npm run build
```

## Integrasi BMKG API

Ubah `WeatherApp.jsx` untuk fetch dari API asli:

```javascript
const loadWeatherData = async () => {
  const response = await fetch(
    `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=${adm4Code}`
  );
  const data = await response.json();
  // Process data...
};
```

## TODO

- [ ] Integrate with real BMKG API
- [ ] Add Leaflet library to package.json
- [ ] Setup build configuration (Webpack/Vite)
- [ ] Add TypeScript types
- [ ] Add unit tests
- [ ] Add dark mode toggle
- [ ] Implement geolocation feature
- [ ] Add PWA support
- [ ] Caching layer untuk API calls
