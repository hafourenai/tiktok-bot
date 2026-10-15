# Converter Web + Weather Viewer

Extended version of [p2r3/convert](https://github.com/p2r3/convert) dengan tambahan **Weather Forecast Viewer** untuk Indonesia.

## Features

### File Converter
- Universal file format converter (hundreds of formats supported)
- Client-side processing (privacy-first)
- Drag-and-drop interface
- Multiple file support

### Weather Forecast
- Real-time weather data from BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)
- Location search by name
- GPS-based weather lookup
- Hourly forecast timeline
- Mobile-responsive design

## Tech Stack

- **Frontend**: Preact + TypeScript + Vite
- **Build**: Bun
- **APIs**: 
  - BMKG (Indonesian Weather Service)
  - OpenStreetMap Nominatim (Geocoding)
  - Wilayah.id (Indonesian Administrative Divisions)

## Installation

### Prerequisites
- Bun 1.0+ ([install](https://bun.sh))
- Node.js 18+ (as fallback)

### Local Development

```bash
# Clone
git clone <repository-url>
cd converter-web

# Install dependencies
bun install

# Run development server
bun run dev
```

Dev server runs on `http://localhost:5173`

## Build

```bash
# Full build (assemble all converters + type check + bundle)
bun run build

# Or step by step:
bun run build:assemble --all
bun run build:check
bun run build
```

Output: `dist/` folder

## Deployment

### Vercel (Recommended)

```bash
# Deploy using Vercel CLI
vercel

# Or connect GitHub repo to Vercel dashboard
```

Config via `vercel.json`:
- Build command: `bun run build:assemble --all && bun run build`
- Output directory: `dist`
- Install command: `bun install`

### Docker

```bash
# Development
docker compose -f docker/docker-compose.yml up -d

# Production
docker compose -f docker/docker-compose.yml -f docker/docker-compose.override.yml up --build -d
```

Accessible at `http://localhost:8080/convert/`

### Static Hosting

Any HTTP server can serve the `dist/` folder:

```bash
# Python
python -m http.server --directory dist 8000

# Node.js (with serve)
npx serve dist -l 3000

# Nginx
# Copy dist/ to /var/www/html/
```

## Project Structure

```
converter-web/
├── src/
│   ├── ui/
│   │   ├── pages/
│   │   │   ├── Upload/           (Upload page)
│   │   │   └── Conversion/
│   │   │       ├── index.tsx      (Original converter)
│   │   │       ├── TabbedPage.tsx (NEW: Tab wrapper)
│   │   │       └── TabbedPage.css
│   │   ├── components/
│   │   │   ├── Conversion/        (Converter UI)
│   │   │   └── Weather/           (NEW: Weather UI)
│   │   │       ├── WeatherViewer.tsx
│   │   │       └── WeatherStyles.css
│   │   ├── AppState.ts
│   │   └── index.tsx
│   ├── services/
│   │   └── bmkg-api.ts            (NEW: Weather API service)
│   ├── handlers/                  (Conversion handlers)
│   ├── Converter.ts
│   └── ... (other core files)
├── public/                        (Static assets)
├── vercel.json                    (Vercel config)
├── vite.config.js
├── tsconfig.json
├── package.json
└── docker-compose.yml
```

## Usage

### File Converter Tab

1. Click **File Converter** tab
2. Upload or drag files
3. Select input format (auto-detected)
4. Click **Next**
5. Select output format
6. Click **Convert**
7. Download result

### Weather Forecast Tab

1. Click **Weather Forecast** tab
2. **Option A**: Search location by name
   - Type location name
   - Select from suggestions
3. **Option B**: Use GPS
   - Click "Current Location"
   - Allow browser to access location
4. View forecast:
   - Current weather card
   - Hourly timeline
   - Detailed metrics (humidity, wind speed)

## Environment Variables

Copy `.env.example` to `.env` (optional for development):

```bash
cp .env.example .env
```

APIs used are public and free, no authentication required.

## Performance

- Converter: Optimized for large files (up to browser limits)
- Weather: Sub-1s API response times
- Bundle size: ~2.5MB (gzipped ~800KB)
- Rendering: <100ms for weather UI

## Browser Support

- Chrome/Edge 88+
- Firefox 85+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Contributing

Same as original [p2r3/convert](https://github.com/p2r3/convert):

- Add new format handlers in `src/handlers/`
- Run tests: `bun test`
- Follow coding style with `bun run fmt` and `bun run lint`

## Limitations

### Converter
- File size limited by browser memory (typically 1-4GB depending on device)
- Some complex formats may have quality trade-offs

### Weather
- Indonesia only (uses BMKG data)
- Updates every 6 hours from BMKG
- Requires internet connection
- GPS accuracy depends on device

## License

Same as [p2r3/convert](https://github.com/p2r3/convert) - GPL-2.0

## Credits

- **Converter**: [p2r3/convert](https://github.com/p2r3/convert)
- **Weather Data**: [BMKG](https://data.bmkg.go.id)
- **Location Services**: [OpenStreetMap](https://www.openstreetmap.org), [Wilayah.id](https://wilayah.id)

## Troubleshooting

### Build fails with "bun not found"
Install Bun: `curl -fsSL https://bun.sh/install | bash`

### Weather API returns 404
Location not in BMKG database. Try searching nearby major city.

### Converter hangs on large files
Browser memory limit reached. Try smaller files or use desktop version.

### Vercel deployment fails
Ensure `bun` is installed in Vercel environment. Check build logs for details.

## Development

### Adding new weather features

1. Create component in `src/ui/components/Weather/`
2. Add API calls to `src/services/bmkg-api.ts`
3. Import and use in `WeatherViewer.tsx`
4. Style with CSS in same folder

### Testing weather service

```typescript
import { getWeatherByCode, searchLocations } from "src/services/bmkg-api.ts";

// Search locations
const results = await searchLocations("Jakarta");

// Get weather by code
const weather = await getWeatherByCode("31.71.03.1001");
```

---

**Need help?** Check [original repo issues](https://github.com/p2r3/convert/issues) or create new issue in this fork.
