# Integrasi React Weather Components ke Bot Python

## Struktur File yang Dibuat

```
src/react/
├── WeatherCard.jsx          # Komponen kartu cuaca utama
├── WeatherCard.css          # Styling kartu
├── WeatherMap.jsx           # Komponen peta interaktif
├── WeatherMap.css           # Styling peta
├── WeatherForecast.jsx      # Komponen timeline prakiraan
├── WeatherForecast.css      # Styling timeline
├── WeatherApp.jsx           # Aplikasi lengkap
├── WeatherApp.css           # Styling app
├── WeatherAPIClient.js      # API client untuk backend
├── index.js                 # Export components
└── README.md                # Dokumentasi
```

## Setup Development

### 1. Install Dependencies

```bash
cd bot_honey
npm install react react-dom
npm install --save-dev @vitejs/plugin-react
```

### 2. Buat Vite Config (untuk development)

```bash
# Jika belum ada vite.config.js, buat:
npm install --save-dev vite
```

**vite.config.js:**
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
```

### 3. Buat Entry Point HTML

**index.html:**
```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Prakiraan Cuaca Indonesia</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="src/react/main.jsx"></script>
</body>
</html>
```

**src/react/main.jsx:**
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import WeatherApp from './WeatherApp'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WeatherApp apiBaseUrl="http://localhost:5000" />
  </React.StrictMode>
)
```

### 4. Update package.json

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "leaflet": "^1.9.4"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
```

```bash
npm install
```

## Backend Integration

### Flask API Endpoints (Python)

Tambahkan ke `bot.py` atau `callback_service.py`:

```python
from flask import Flask, jsonify, request
from weather_card import generate_weather_card
from src.bmkg_location_resolver import resolver
import io
import base64

app = Flask(__name__)

@app.route('/api/weather')
def get_weather():
    """Fetch weather data by ADM4 code"""
    adm4 = request.args.get('adm4')
    try:
        # Fetch dari BMKG
        data = resolver.fetch_weather(adm4)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/weather/coordinates')
def get_weather_by_coords():
    """Fetch weather data by GPS coordinates"""
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    try:
        # Resolve koordinat ke lokasi
        location = resolver.reverse_geocode(lat, lon)
        data = resolver.fetch_weather(location['adm4'])
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/weather/locations')
def get_all_locations():
    """Get weather for multiple locations"""
    try:
        # Fetch cuaca untuk lokasi-lokasi utama Indonesia
        locations = resolver.get_major_locations()
        return jsonify(locations)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/locations/search')
def search_locations():
    """Search locations by name"""
    query = request.args.get('q', '')
    try:
        results = resolver.search_locations(query)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/weather/card')
def get_weather_card():
    """Generate shareable weather card image"""
    adm4 = request.args.get('adm4')
    try:
        data = resolver.fetch_weather(adm4)
        card_image = generate_weather_card(data, adm4)
        return card_image.getvalue(), 200, {'Content-Type': 'image/jpeg'}
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

## Development & Testing

### Run Development Server

```bash
# Terminal 1: Backend Python
cd bot_honey
python app.py  # atau callback_service.py yang sudah di-setup Flask

# Terminal 2: Frontend React
cd bot_honey
npm run dev
```

Buka `http://localhost:3000`

### Production Build

```bash
npm run build
# Output: dist/
```

## Fitur-Fitur

### ✅ Implemented
- [x] Kartu cuaca responsif dengan glassmorphism
- [x] Peta interaktif dengan Leaflet (atau canvas fallback)
- [x] Timeline prakiraan per periode
- [x] Sidebar lokasi terdekat
- [x] Error & loading states
- [x] Mobile-optimized
- [x] Dark-mode ready styles
- [x] Animasi halus

### 📋 TODO
- [ ] Integrate real BMKG API
- [ ] Add geolocation feature
- [ ] Implement caching
- [ ] Add TypeScript types
- [ ] Unit & e2e tests
- [ ] Dark mode toggle
- [ ] Share weather card
- [ ] PWA support
- [ ] Multi-language i18n

## Performance Tips

1. **Lazy Load Leaflet**: WeatherMap menggunakan dynamic import
2. **Image Optimization**: Emoji digunakan daripada PNG
3. **CSS-in-JS**: Inline styles untuk smooth animations
4. **Debounce Search**: Untuk location search queries
5. **Virtual Scrolling**: Untuk daftar lokasi panjang

## Troubleshooting

### Port 5000 sudah dipakai
```bash
# Gunakan port lain di Flask
python app.py --port 5001

# Update vite.config.js
proxy: {
  '/api': {
    target: 'http://localhost:5001'
  }
}
```

### Module not found errors
```bash
npm install
npm install leaflet
```

### CORS errors
Tambahkan di Flask:
```python
from flask_cors import CORS
CORS(app)
```

## File Size & Performance

- **WeatherCard.jsx**: ~3KB
- **WeatherMap.jsx**: ~4KB  
- **WeatherForecast.jsx**: ~3KB
- **WeatherApp.jsx**: ~5KB
- **CSS**: ~12KB (dapat diminimalisir)
- **Total (gzipped)**: ~15-18KB

## Next Steps

1. Setup Flask API endpoints
2. Connect ke real BMKG resolver
3. Deploy ke production environment
4. Add analytics & error tracking
5. Setup CI/CD pipeline
