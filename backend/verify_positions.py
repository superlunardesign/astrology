"""
Independent check of the positions the app calculates

Nothing here uses Swiss Ephemeris. Planet positions are recomputed from JPL's
approximate Keplerian elements (the published 1800-2050 table), and the
date-to-Julian-Day chain is checked against fixed astronomical constants. If
these agree with the app to a few arc minutes, the ephemeris and the timezone
handling are sound and any disagreement with other software is in the chart
data, not the transit math.

Run: python verify_positions.py
"""
import math
from datetime import datetime

from ephemeris_manager import EphemerisManager

# JPL approximate elements, epoch J2000, valid 1800-2050:
# a (AU), e, I (deg), L (deg), longitude of perihelion, longitude of node,
# each with its rate per Julian century
ELEMENTS = {
    'Mercury': (0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749,
                252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081),
    'Venus':   (0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890,
                181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418),
    'Earth':   (1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668,
                100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0),
    'Mars':    (1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131,
                -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343),
    'Jupiter': (5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714,
                34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106),
    'Saturn':  (9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609,
                49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794),
    'Uranus':  (19.18916464, -0.00196176, 0.04725744, -0.00004397, 0.77263783, -0.00242939,
                313.23810451, 428.48202785, 170.95427630, 0.40805281, 74.01692503, 0.04240589),
    'Neptune': (30.06992276, 0.00026291, 0.00859048, 0.00005105, 1.77004347, 0.00035372,
                -55.12002969, 218.45945325, 44.96476227, -0.32241464, 131.78422574, -0.00508664),
}

# General precession from J2000, arcseconds per Julian year
PRECESSION_ARCSEC_PER_YEAR = 50.2879


def heliocentric_xyz(planet, centuries):
    """Position in the J2000 ecliptic frame, from Keplerian elements"""
    (a0, da, e0, de, i0, di, l0, dl, peri0, dperi, node0, dnode) = ELEMENTS[planet]

    a = a0 + da * centuries
    e = e0 + de * centuries
    inc = math.radians(i0 + di * centuries)
    mean_long = l0 + dl * centuries
    peri = peri0 + dperi * centuries
    node = node0 + dnode * centuries

    mean_anomaly = math.radians((mean_long - peri + 180) % 360 - 180)
    arg_peri = math.radians(peri - node)
    node = math.radians(node)

    # Kepler's equation
    eccentric = mean_anomaly
    for _ in range(60):
        eccentric -= ((eccentric - e * math.sin(eccentric) - mean_anomaly)
                      / (1 - e * math.cos(eccentric)))

    # Position in the orbital plane, then rotated into the ecliptic
    x_orbit = a * (math.cos(eccentric) - e)
    y_orbit = a * math.sqrt(1 - e * e) * math.sin(eccentric)

    cos_w, sin_w = math.cos(arg_peri), math.sin(arg_peri)
    cos_o, sin_o = math.cos(node), math.sin(node)
    cos_i, sin_i = math.cos(inc), math.sin(inc)

    x = ((cos_w * cos_o - sin_w * sin_o * cos_i) * x_orbit
         + (-sin_w * cos_o - cos_w * sin_o * cos_i) * y_orbit)
    y = ((cos_w * sin_o + sin_w * cos_o * cos_i) * x_orbit
         + (-sin_w * sin_o + cos_w * cos_o * cos_i) * y_orbit)
    z = (sin_w * sin_i) * x_orbit + (cos_w * sin_i) * y_orbit

    return x, y, z


def geocentric_longitude(planet, jd):
    """Apparent ecliptic longitude of date, degrees"""
    centuries = (jd - 2451545.0) / 36525.0

    if planet == 'Sun':
        ex, ey, ez = heliocentric_xyz('Earth', centuries)
        x, y = -ex, -ey
    else:
        px, py, pz = heliocentric_xyz(planet, centuries)
        ex, ey, ez = heliocentric_xyz('Earth', centuries)
        x, y = px - ex, py - ey

    longitude = math.degrees(math.atan2(y, x))

    # J2000 elements give longitude in the J2000 frame; the zodiac is measured
    # from the equinox of date, so add the precession since J2000
    longitude += PRECESSION_ARCSEC_PER_YEAR * ((jd - 2451545.0) / 365.25) / 3600.0

    return longitude % 360


SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']


def format_position(longitude):
    degrees = longitude % 30
    minutes = (degrees % 1) * 60
    return f"{int(degrees):2d}°{int(minutes):02d}' {SIGNS[int(longitude / 30)]}"


def main():
    em = EphemerisManager()
    failures = []

    print(f"\nEphemeris in use: {em.ephemeris_source}")
    if 'Moshier' in em.ephemeris_source:
        print("  (the .se1 files in ephemeris/ are missing - positions still")
        print("   agree to about an arc second, but Chiron is unavailable)")

    print("\nJulian Day chain (fixed astronomical constants)")
    print("-" * 72)
    checks = [
        ('J2000 epoch', '2000-01-01', '12:00', 'UTC', 2451545.0),
        ('Unix epoch', '1970-01-01', '00:00', 'UTC', 2440587.5),
        # Both of these are noon UTC, so they land on a whole Julian Day
        ('Pacific daylight time (UTC-7)', '2026-09-07', '05:00', 'America/Los_Angeles', 2461291.0),
        ('Pacific standard time (UTC-8)', '2026-12-07', '04:00', 'America/Los_Angeles', 2461382.0),
    ]
    for label, date, time, tz, expected in checks:
        actual = em.get_julian_day(date, time, tz)
        ok = abs(actual - expected) < 1e-6
        print(f"  {'PASS' if ok else 'FAIL'}  {label:32} {actual:.6f} (expected {expected})")
        if not ok:
            failures.append(label)

    print("\nPositions vs an independent Keplerian model")
    print("-" * 72)
    print(f"  {'planet':9} {'app (Swiss Ephemeris)':24} {'independent model':24} diff")

    jd = em.get_julian_day(datetime.now().strftime('%Y-%m-%d'), '12:00', 'America/Los_Angeles')
    for planet in ['Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune']:
        app = em.get_planet_position(planet, jd)['longitude']
        independent = geocentric_longitude(planet, jd)
        diff = abs((app - independent + 180) % 360 - 180) * 60  # arc minutes

        # The model ignores light-time and nutation, so a few arc minutes is
        # expected; anything larger means the app's positions are off
        ok = diff < 15
        if not ok:
            failures.append(planet)
        print(f"  {'PASS' if ok else 'FAIL'} {planet:9} {format_position(app):24} "
              f"{format_position(independent):24} {diff:5.1f}'")

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {', '.join(failures)}")
        raise SystemExit(1)
    print("Positions and time handling verified.")


if __name__ == '__main__':
    main()
