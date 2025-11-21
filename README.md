# Transit Tracker - Relationship Astrology Web App

A web application for tracking transits to multiple natal charts over time, with focus on relationship astrology.

## Features

### Daily Aspect Dashboard
- View all active transits within 3° orb for any date
- See current exact orb (e.g., "0.19°")
- Indicate if APPLYING (→) or SEPARATING (←)
- Display aspect strength as percentage (100% at exact, 0% at 3°)
- Show when aspect goes exact
- Rate significance: CRITICAL, HIGH, MEDIUM, LOW
- Filter challenging vs supportive aspects

### Transit Scanner
- Search forward through date ranges to find exact transits
- Filter by chart type (Christina/Julian/Davison)
- Filter by planets and aspect types
- Sort by date and significance
- Identify optimal windows for important decisions

### Aspect Timeline Calculator
- Complete timeline for any specific transit
- When it enters/leaves different orbs (5°, 3°, 1°)
- Exact date/time
- Days remaining in effect
- Current status and strength

### Compare Charts
- View all three charts side-by-side
- Identify overlapping challenging aspects
- Find "crisis windows" and "opportunity windows"

## Tech Stack

- **Backend**: Python 3.11 + Flask + Swiss Ephemeris (pyswisseph)
- **Frontend**: HTML/CSS/JavaScript (vanilla, no framework needed)
- **Deployment**: Render
- **Astronomical Data**: Swiss Ephemeris (highly accurate)

## Quick Start

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the app:**
```bash
cd backend
python app.py
```

3. **Open browser:**
Navigate to http://localhost:5000

That's it! The frontend is served directly by Flask.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

Quick deploy to Render:
1. Push to GitHub
2. Connect to Render
3. Render auto-detects `render.yaml` and deploys

## API Endpoints

All endpoints return JSON.

### Charts
- `GET /api/charts` - List available charts
- `GET /api/chart/<chart_key>` - Get natal chart data

### Daily Dashboard
- `GET /api/dashboard/<chart_key>?date=YYYY-MM-DD&max_orb=3`
  - Returns all active aspects for a specific date
  - Default: today, 3° orb

### Transit Scanner
- `GET /api/scan/<chart_key>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  - Find upcoming exact aspects
  - Optional filters: `planets=Pluto,Saturn&aspects=Square,Opposition&min_significance=HIGH`

### Aspect Timeline
- `GET /api/timeline/<chart_key>/<transit_planet>/<natal_point>/<aspect_name>?reference_date=YYYY-MM-DD`
  - Get complete timeline for a specific aspect
  - Example: `/api/timeline/julian/Pluto/Mercury/Conjunction`

### Compare Charts
- `GET /api/compare?date=YYYY-MM-DD&charts=christina,julian,davison`
  - Compare transits across multiple charts

### Date Range Summary
- `GET /api/date-range/<chart_key>?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  - Get daily summaries over a date range

## Birth Data

Three charts are pre-configured:

- **Christina**: March 26, 1992, 9:04 AM, Indianapolis, IN
- **Julian**: February 16, 2002, 12:30 AM, Olympia, WA
- **Davison** (Midpoint): March 7, 1997, 3:58 AM, Lusk, WY

## Configuration

Birth data and settings are in `backend/config.py`:
- Natal chart data (dates, times, locations)
- Planets to track
- Aspects and orbs
- Significance ratings

## Calculation Details

### Aspects Tracked
- Conjunction (0°) - orb 3°
- Sextile (60°) - orb 3°
- Square (90°) - orb 3°
- Trine (120°) - orb 3°
- Opposition (180°) - orb 3°

### Planets Tracked
- **Transiting**: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Nodes
- **Natal Points**: All planets + Ascendant, Descendant, MC, IC

### Applying vs Separating
- **Applying**: Aspect is getting closer to exact (orb decreasing)
- **Separating**: Aspect is moving away from exact (orb increasing)
- Determined by comparing current orb to orb 24 hours later

### Significance Ratings
- **CRITICAL**: Outer planets (Pluto, Saturn, Uranus, Neptune) to personal planets or angles
- **HIGH**: Outer planets to inner planets, Jupiter to Sun/Moon/Venus
- **MEDIUM**: Venus/Mars to relationship points, Jupiter to other points
- **LOW**: Fast-moving transits (Sun, Mercury) unless to critical points

## Testing Specific Transits

To verify calculations against known transits:

```bash
cd backend
python test_specific_transits.py
```

This will show:
- Julian's Pluto conjunct Mercury (currently active)
- Saturn square North Node timeline
- Upcoming exact transits

## File Structure

```
astrology/
├── backend/
│   ├── app.py                    # Flask API
│   ├── config.py                 # Configuration & natal data
│   ├── ephemeris_manager.py      # Swiss Ephemeris wrapper
│   ├── natal_charts.py           # Natal chart calculations
│   ├── transit_calculator.py     # Core transit logic
│   ├── test_specific_transits.py # Test script
│   └── debug_saturn.py           # Saturn debug script
├── frontend/
│   └── index.html                # Single-page app
├── requirements.txt              # Python dependencies
├── render.yaml                   # Render deployment config
├── Procfile                      # Alternative deployment config
├── README.md                     # This file
└── DEPLOYMENT.md                 # Deployment guide
```

## Swiss Ephemeris

The app uses Swiss Ephemeris (via pyswisseph) for astronomical calculations:
- Industry standard for astrology software
- Extremely accurate planetary positions
- Ephemeris files are automatically downloaded on first run
- Data stored in `ephemeris/` directory

## License

For personal use. Birth data is private and should not be shared publicly.
