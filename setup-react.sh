#!/bin/bash
# Instalasi quick start untuk React Weather Components

echo "🌤️  Installing React Weather Components..."
echo ""

# 1. Install dependencies
echo "📦 Installing npm dependencies..."
npm install react react-dom leaflet

echo "🔧 Installing dev dependencies..."
npm install --save-dev vite @vitejs/plugin-react

# 2. Info
echo ""
echo "✅ Setup selesai!"
echo ""
echo "📍 File yang dibuat:"
echo "   - src/react/WeatherCard.jsx (Komponen kartu cuaca)"
echo "   - src/react/WeatherMap.jsx (Peta interaktif)"
echo "   - src/react/WeatherForecast.jsx (Timeline prakiraan)"
echo "   - src/react/WeatherApp.jsx (Aplikasi lengkap)"
echo "   - WeatherAPIClient.js (API integration layer)"
echo ""
echo "📋 Dokumentasi:"
echo "   - src/react/README.md"
echo "   - REACT_SETUP.md"
echo ""
echo "🚀 Next steps:"
echo "   1. npm run dev        # Jalankan development server"
echo "   2. Buka http://localhost:3000"
echo "   3. Setup Flask API endpoints (lihat REACT_SETUP.md)"
echo ""
