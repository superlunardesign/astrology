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
- Determined by comparing the current orb to the orb a few hours later, from the
  planet's real position - so a planet that stations flips to separating the
  moment it turns, even though its listed speed is near zero

### Exactness
- An aspect is **exact** only at the moment it reaches 0°00' - the transiting
  planet crossing the aspect point. Exact dates come from that crossing, found
  by bisection, never from "the orb stopped shrinking".
- A planet that stations while still applying **never goes exact on that pass**.
  It flips from applying to separating at the station, and the reported exact
  date is the later pass where it truly perfects (often after it turns direct
  again). The station itself is listed separately, never as an exact date.
- A retrograde series over the same point produces three exact hits, and each
  one is reported.
- Applying/separating and "will it perfect again?" are separate questions. An
  aspect can be separating right now and still have another exact pass ahead,
  because the planet stations and travels back over the same point. So each
  aspect reports: **current state** (applying/separating), **previous exact**
  (if one happened), **next exact** (if another pass is coming), and the
  **station** in between that turns the planet around.
- The next pass is quoted when the aspect is applying, or when nothing has
  perfected yet. Once an aspect has perfected, the next pass is only quoted for
  a slow planet coming back over the point - within six months, or with a
  station in between. A fast planet's next pass is just its regular cycle.
- A slow planet with a hit behind it and nothing ahead in a three-year search is
  marked **(final pass)** - it is done with that aspect.
- **(Rx)** after a transiting planet means it is retrograde now; **(SR)**/**(SD)**
  mean it stations retrograde/direct that day. **(Rx)** after an exact date means
  the aspect perfects while the planet is retrograde. Direction changes between
  today and a quoted date are listed with it - with none listed, the planet holds
  the same direction throughout.
- The true lunar node wobbles direct/retrograde every few days, so its direction
  is read across the surrounding week rather than from one day's speed.
- The Davison chart is listed as "Davison (Midpoint)" in the chart pickers, but
  copy/paste output names it in full - "Davison Relationship Chart of Julian &
  Christina" in headings, "the Davison chart's natal Pluto" inline.

### Significance Ratings
- **CRITICAL**: Outer planets (Pluto, Saturn, Uranus, Neptune) to personal planets or angles
- **HIGH**: Outer planets to inner planets, Jupiter to Sun/Moon/Venus
- **MEDIUM**: Venus/Mars to relationship points, Jupiter to other points
- **LOW**: Fast-moving transits (Sun, Mercury) unless to critical points

### Transit Journal
Day-by-day reads over 7, 10 or 14 days. Each day lists the Moon's sign, ingress
and every aspect it perfects (timed to the minute from real 0°00' crossings),
any planet that stations that day, transits entering orb / going exact / leaving
orb, and every active transit with its current orb. The overview above the daily
entries lists each transit's orb window and **every** perfection inside it - a
retrograde series shows all its passes, and an aspect the planet stations short
of shows "none in this orb window" plus the date it finally perfects.

Journals are cached in memory (last 24), and comparison mode requests one chart
at a time so a slow instance never has to answer one long multi-chart request.

## Testing Specific Transits

To verify calculations against known transits:

```bash
cd backend
python test_specific_transits.py   # known transits, printed for eyeballing
python test_exactness.py           # exactness/retrograde regression checks
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
