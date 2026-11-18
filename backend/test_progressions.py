"""
Progression and solar arc accuracy checks

These test the technique itself against its own definitions, not against the
code's opinion of them:

  - a progressed chart for the Nth birthday is the sky N days after birth
  - the solar arc is the progressed Sun's distance from the natal Sun, so the
    directed Sun must land exactly on the progressed Sun
  - every directed point moves by that same arc, and no other
  - the rates come out right: about a degree a year for the progressed Sun and
    the arc, about a degree a month for the progressed Moon
  - every exact date reported really has the aspect at 0°00' on that date
  - progressed positions match an independent Keplerian model

Run: python test_progressions.py
"""
from datetime import datetime, timedelta

from config import ASPECTS, NATAL_CHARTS
from ephemeris_manager import EphemerisManager
from progressions import ProgressionCalculator, TROPICAL_YEAR_DAYS
from transit_calculator import TransitCalculator
from verify_positions import geocentric_longitude

tc = TransitCalculator()
pc = ProgressionCalculator(tc)
em = EphemerisManager()

CHART = 'christina'
DATE = '2026-09-07'
failures = []


def check(name, condition, detail=''):
    print(f"  {'PASS' if condition else 'FAIL'}  {name} {detail if not condition else ''}")
    if not condition:
        failures.append(name)


def separation(a, b):
    """Smallest angle between two longitudes"""
    return abs((a - b + 180) % 360 - 180)


print("\nA progressed chart is the sky N days after birth")
print("-" * 72)
birth_jd = pc.birth_julian_day(CHART)
birth = NATAL_CHARTS[CHART]
birth_dt = datetime.strptime(f"{birth['date']} {birth['time']}", '%Y-%m-%d %H:%M')

for age in [10, 34]:
    # The exact moment of the Nth birthday by the same tropical year the
    # progression rate uses
    birthday_jd = birth_jd + age * TROPICAL_YEAR_DAYS
    progressed_jd = pc.progressed_julian_day(CHART, birthday_jd)

    check(f'age {age}: progressed moment is birth + {age} days',
          abs(progressed_jd - (birth_jd + age)) < 1e-6,
          f'(off by {(progressed_jd - (birth_jd + age)) * 24:.4f} hours)')

    # and the positions there are just the ephemeris on that day
    for planet in ['Sun', 'Moon', 'Mars']:
        direct = em.get_planet_position(planet, birth_jd + age)['longitude']
        through_progression = pc.progressed_body(CHART, planet)(birthday_jd)['longitude']
        check(f'age {age}: progressed {planet} equals the ephemeris that day',
              separation(direct, through_progression) < 1e-9)

print("\nSolar arc is the progressed Sun's distance from the natal Sun")
print("-" * 72)
jd = em.get_julian_day(DATE, '12:00', 'America/Los_Angeles')
arc = pc.solar_arc_at(CHART, jd)
directed = pc.directed_chart(CHART, DATE)
progressed = pc.progressed_chart(CHART, DATE)

check('the directed Sun lands on the progressed Sun',
      separation(directed['positions']['Sun']['longitude'],
                 progressed['positions']['Sun']['longitude']) < 1e-9,
      f"({directed['positions']['Sun']['longitude']:.6f} vs "
      f"{progressed['positions']['Sun']['longitude']:.6f})")

moved_by = {
    point: separation(position['longitude'] + 360,
                      pc.natal_longitude(CHART, point) + arc + 360)
    for point, position in directed['positions'].items()
}
check('every directed point moves by exactly the same arc',
      max(moved_by.values()) < 1e-9,
      f'(worst {max(moved_by.values()):.9f}°)')

print("\nThe rates come out right")
print("-" * 72)
one_year_later = em.get_julian_day('2027-09-07', '12:00', 'America/Los_Angeles')
arc_next_year = pc.solar_arc_at(CHART, one_year_later)
arc_rate = arc_next_year - arc
check('solar arc advances about a degree a year', 0.95 < arc_rate < 1.02,
      f'({arc_rate:.4f}°/yr)')

moon_now = pc.progressed_body(CHART, 'Moon')(jd)['longitude']
moon_next_year = pc.progressed_body(CHART, 'Moon')(one_year_later)['longitude']
moon_rate = (moon_next_year - moon_now) % 360
check('progressed Moon advances 12-15° a year', 12 < moon_rate < 15,
      f'({moon_rate:.3f}°/yr)')
check('progressed Moon covers a sign in about 2.5 years',
      2.0 < 30 / moon_rate < 3.0, f'({30 / moon_rate:.2f} years per sign)')

sun_rate = (pc.progressed_body(CHART, 'Sun')(one_year_later)['longitude']
            - pc.progressed_body(CHART, 'Sun')(jd)['longitude']) % 360
check('progressed Sun advances about a degree a year', 0.95 < sun_rate < 1.02,
      f'({sun_rate:.4f}°/yr)')

print("\nEvery exact date reported really is 0°00'")
print("-" * 72)
report = pc.generate_report(CHART, DATE)
checked = 0
worst = 0.0

for bucket, items in report['aspects'].items():
    for item in items:
        aspect_angle = ASPECTS[item['aspect']]['angle']

        if bucket == 'directed_to_natal':
            body = pc.directed_body(CHART, item['moving_point'])
            target = pc.natal_longitude(CHART, item['target_point'])
        elif bucket == 'progressed_to_natal':
            body = pc.progressed_body(CHART, item['moving_point'])
            target = pc.natal_longitude(CHART, item['target_point'])
        else:
            # progressed to progressed: the target moves too, so it is only
            # meaningful at the moment being reported
            continue

        for hit in [item['previous_exact'], item['next_exact']]:
            if not hit:
                continue
            hit_jd = em.get_julian_day(hit['date'], '12:00', 'America/Los_Angeles')
            orb = tc.calculate_aspect_orb(body(hit_jd)['longitude'], target, aspect_angle)
            worst = max(worst, orb)
            checked += 1

check(f'all {checked} reported exact dates land on the aspect',
      worst < 0.02, f'(worst {worst * 60:.2f} arc minutes)')

print("\nProgressed positions match an independent model")
print("-" * 72)
progressed_jd = pc.progressed_julian_day(CHART, jd)
worst_model = 0.0
for planet in ['Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter']:
    ours = em.get_planet_position(planet, progressed_jd)['longitude']
    independent = geocentric_longitude(planet, progressed_jd)
    worst_model = max(worst_model, separation(ours, independent) * 60)
check('progressed planets agree with the Keplerian model', worst_model < 15,
      f'(worst {worst_model:.1f} arc minutes)')

print("\nAgreement with Time Nomad")
print("-" * 72)
# Values read off the Davison progressed chart in Time Nomad for 2027-01-01.
# The progressed Sun pins the solar arc (the arc is defined as its distance
# from the natal Sun), and the MC pins how the angles are advanced - the RA
# based methods land over a degree away, so this also fixes the method.
TIME_NOMAD = {'date': '2027-01-01', 'sun': 16 + 31 / 60, 'mc': 17 + 19 / 60}

reference_jd = em.get_julian_day(TIME_NOMAD['date'], '12:00', 'America/Los_Angeles')
their_sun = pc.progressed_body('davison', 'Sun')(reference_jd)['longitude'] % 30
their_mc = (pc.natal_longitude('davison', 'MC')
            + pc.solar_arc_at('davison', reference_jd)) % 30

check('progressed Sun matches Time Nomad',
      abs(their_sun - TIME_NOMAD['sun']) * 60 < 2,
      f"(ours {their_sun:.4f}°, theirs {TIME_NOMAD['sun']:.4f}°, "
      f"{(their_sun - TIME_NOMAD['sun']) * 60:+.2f} arc minutes)")
check('progressed MC matches Time Nomad, so solar arc in longitude is the method',
      abs(their_mc - TIME_NOMAD['mc']) * 60 < 2,
      f"(ours {their_mc:.4f}°, theirs {TIME_NOMAD['mc']:.4f}°, "
      f"{(their_mc - TIME_NOMAD['mc']) * 60:+.2f} arc minutes)")

print("\nEvery chart progresses, including the Davison")
print("-" * 72)
for chart_key in NATAL_CHARTS:
    try:
        result = pc.generate_report(chart_key, DATE)
        has_text = 'PROGRESSIONS & SOLAR ARC' in result['plain_text']
        check(f'{chart_key} progresses', has_text and result['years_elapsed'] > 0,
              f"({result['years_elapsed']:.1f} yrs)")
    except Exception as error:
        check(f'{chart_key} progresses', False, f'({error})')

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    raise SystemExit(1)
print("Progressions and solar arc verified.")
