"""
Exactness and retrograde tests

The rule under test: an aspect is exact only at the moment it reaches 0°00'.
A planet that stations while applying flips to separating without ever going
exact, and that station date must never be reported as an exact date.

Run: python test_exactness.py
"""
from datetime import datetime, timedelta

from config import ASPECTS
from transit_calculator import TransitCalculator, EXACT_TOLERANCE_DEG

tc = TransitCalculator()
failures = []


def check(name, condition, detail=''):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def orb_at(transit_planet, natal_long, aspect_name, dt):
    longitude = tc.get_longitude_at(transit_planet, dt)
    return tc.calculate_aspect_orb(longitude, natal_long, ASPECTS[aspect_name]['angle'])


print("\nUranus stations retrograde 09-10-2026 while applying to Christina's Sun")
print("-" * 72)
natal_sun = tc.ncm.get_natal_position('christina', 'Sun')
station_orb = orb_at('Uranus', natal_sun, 'Sextile', datetime(2026, 9, 10, 12, 0))
check('the station is well short of exact', station_orb > 0.4, f'(orb {station_orb:.3f}°)')

exact_date, exact_orb = tc.find_exact_aspect_date(
    'christina', 'Uranus', 'Sun', 'Sextile', '2026-09-04', max_days=120
)
check('no exact date is invented for the station',
      exact_date != '2026-09-10', f'(got {exact_date})')
check('nothing perfects within 120 days', exact_date is None, f'(got {exact_date})')

dashboard = tc.get_daily_dashboard('christina', '2026-09-04', max_orb=3)
uranus_sun = next(a for a in dashboard['aspects']
                  if a['transit_planet'] == 'Uranus' and a['natal_point'] == 'Sun'
                  and a['aspect'] == 'Sextile')
check('it is still applying on 09-04', uranus_sun['is_applying'])
check('the quoted exact date is the real perfection, not the station',
      uranus_sun['exact_date'] == '2027-06-02', f"(got {uranus_sun['exact_date']})")
check('the station is called out in the range',
      any(s['date'] == '2026-09-10' and s['type'] == 'SR' for s in uranus_sun['stations']),
      f"(got {uranus_sun['stations']})")

print("\nEvery reported perfection really is 0°00'")
print("-" * 72)
def tightest_orb(aspect, timestamp, to_the_minute):
    # Slow planets are quoted to the day, so check the whole day for those
    moments = [timestamp] if to_the_minute else [
        timestamp + timedelta(hours=hour) for hour in range(-12, 13)
    ]
    return min(orb_at(aspect['transit_planet'], aspect['natal_longitude'], aspect['aspect'], moment)
               for moment in moments)


worst = 0.0
for chart in ['christina', 'julian']:
    for aspect in tc.get_daily_dashboard(chart, '2026-09-04', max_orb=3)['aspects']:
        quotes = []
        if aspect.get('last_exact'):
            quotes.append((aspect['last_exact']['datetime'], True))
        if aspect['exact_date']:
            quotes.append((aspect['exact_datetime'] or aspect['exact_date'] + ' 12:00',
                           bool(aspect['exact_datetime'])))

        for stamp, to_the_minute in quotes:
            worst = max(worst, tightest_orb(
                aspect, datetime.strptime(stamp, '%Y-%m-%d %H:%M'), to_the_minute))
check('all quoted hits land on 0°00'"'", worst < 2 * EXACT_TOLERANCE_DEG, f'(worst {worst:.5f}°)')

print("\nRetrograde passes are detected and marked")
print("-" * 72)
natal_saturn_moon = tc.ncm.get_natal_position('christina', 'Moon')
passes = tc.find_exact_crossings('Saturn', natal_saturn_moon, 90,
                                 datetime(2026, 1, 1), datetime(2027, 6, 1))
check('Saturn squares the natal Moon three times', len(passes) == 3, f'(got {len(passes)})')
check('the middle pass is the retrograde one',
      [p['retrograde'] for p in passes] == [False, True, False],
      f"(got {[p['retrograde'] for p in passes]})")
check('every pass is exact to the arc second',
      all(p['orb'] < 0.001 for p in passes), f"(got {[round(p['orb'], 6) for p in passes]})")

print("\nApplying and separating stay right through a station")
print("-" * 72)
before = tc.find_aspects('christina', '2026-09-08', max_orb=3)
after = tc.find_aspects('christina', '2026-09-12', max_orb=3)


def uranus_sextile_sun(aspects):
    return next(a for a in aspects if a['transit_planet'] == 'Uranus'
                and a['natal_point'] == 'Sun' and a['aspect'] == 'Sextile')


check('applying before the station', uranus_sextile_sun(before)['is_applying'])
check('separating after it', not uranus_sextile_sun(after)['is_applying'])
check('marked direct before', not uranus_sextile_sun(before)['is_retrograde'])
check('marked retrograde after', uranus_sextile_sun(after)['is_retrograde'])
check('copy shows the Rx marker', uranus_sextile_sun(after)['motion_marker'] == '(Rx)',
      f"(got {uranus_sextile_sun(after)['motion_marker']!r})")

print("\nScanner only lists real perfections")
print("-" * 72)
scan = tc.scan_future_transits('christina', '2026-09-04', '2026-12-04', min_significance='LOW')
check('no scanner hit is a station', all(t['exact_orb'] < 0.005 for t in scan),
      f"(worst {max([t['exact_orb'] for t in scan], default=0):.5f}°)")
check('no Uranus station leaked in',
      not any(t['transit_planet'] == 'Uranus' and t['exact_date'] == '2026-09-10' for t in scan))

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    raise SystemExit(1)
print("All exactness checks passed.")
