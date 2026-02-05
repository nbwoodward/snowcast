# Snowcast

A web app that shows which ski resort regions worldwide are most likely to get snow in the next week, using Open-Meteo's free weather API with ensemble forecasts.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Action (Daily CRON)                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ Resort Data │ +  │  Open-Meteo │ →  │ Snow Calculator │  │
│  │   (CSV)     │    │  (REST API) │    │    (Python)     │  │
│  └─────────────┘    └─────────────┘    └────────┬────────┘  │
│                                                  │           │
│                                    ┌─────────────▼─────────┐ │
│                                    │ forecasts.json        │ │
│                                    │ (committed to repo)   │ │
│                                    └─────────────┬─────────┘ │
└──────────────────────────────────────────────────│───────────┘
                                                   │
┌──────────────────────────────────────────────────▼───────────┐
│                    GitHub Pages (Static Site)                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  HTML/JS Frontend                                      │  │
│  │  - Leaflet Map with markers                            │  │
│  │  - Region cards sorted by snow probability             │  │
│  │  - Resort table with filtering                         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Features

- **Interactive Map**: Leaflet.js map with color-coded markers by snow probability
- **Region Overview**: Cards showing 12 major ski regions sorted by snow outlook
- **Resort Details**: Searchable, sortable table of all resorts with 7-day forecasts
- **Daily Updates**: GitHub Action fetches fresh forecasts every day at 6 AM UTC
- **Free**: Uses Open-Meteo's free API - no API keys or cloud costs required

## Data Sources

1. **Open-Meteo** - Free weather API with ensemble forecasts
   - GFS ensemble model with 31 members for probabilistic predictions
   - 7-day forecasts with hourly resolution
   - No API key required

2. **Ski Resorts Data** - Resort locations with lat/lon and elevation
   - 75+ resorts across 12 regions worldwide

## Regions Covered

- European Alps (France, Switzerland, Austria, Italy)
- US Rockies (Colorado, Utah, Wyoming, Montana)
- Canadian Rockies (British Columbia, Alberta)
- Sierra Nevada (California)
- Cascades (Washington, Oregon)
- Northeast USA (Vermont, New Hampshire, Maine)
- Pyrenees (France, Spain, Andorra)
- Scandinavia (Norway, Sweden, Finland)
- Japanese Alps (Honshu, Hokkaido)
- Andes (Chile, Argentina)
- Oceania (Australia, New Zealand)
- Dolomites (Italy)

## Setup

### Prerequisites

- Python 3.11+

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/snowcast.git
   cd snowcast
   ```

2. Install Python dependencies:
   ```bash
   pip install -r scripts/requirements.txt
   ```

3. Run the forecast script:
   ```bash
   python scripts/fetch_forecasts.py
   ```

4. Open the site locally:
   ```bash
   open docs/index.html
   ```

### GitHub Actions Setup

1. Enable GitHub Pages on the `/docs` folder
2. The Action runs automatically daily at 6 AM UTC
3. No secrets or API keys required!

## Snow Probability Algorithm

For each resort, across ensemble members:

1. Fetch temperature and precipitation forecasts
2. Adjust temperature for resort elevation (lapse rate: -6.5°C/1000m)
3. Snow occurs when: temp ≤ 1°C AND precip > 0.5mm
4. Convert precipitation to snow (10:1 ratio)
5. Probability = % of ensemble members showing snow
6. Expected amount = mean across ensembles
7. Confidence interval = P10-P90 range

## Project Structure

```
snowcast/
├── .github/workflows/
│   └── update-forecasts.yml     # Daily CRON job
├── data/
│   ├── resorts.csv              # Ski resort data
│   └── regions.json             # Region bounding boxes
├── scripts/
│   ├── fetch_forecasts.py       # Main script
│   ├── weather_client.py        # Open-Meteo API client
│   ├── snow_calculator.py       # Snow probability algorithm
│   └── requirements.txt         # Python dependencies
├── docs/                        # GitHub Pages static site
│   ├── index.html
│   ├── js/app.js
│   ├── css/style.css
│   └── data/forecasts.json      # Generated daily
└── README.md
```

## Cost

**Free!** Open-Meteo provides 10,000 API requests/day on their free tier, which is more than enough for daily updates of 75 resorts.

## License

MIT

## Credits

- Weather data: [Open-Meteo](https://open-meteo.com/)
- Map: [Leaflet.js](https://leafletjs.com/)
- Base tiles: [OpenStreetMap](https://www.openstreetmap.org/)
