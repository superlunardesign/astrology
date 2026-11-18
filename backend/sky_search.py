"""
Sky searches: where a planet has been, and when it was there.

The transit calculator answers questions about a chart - what the sky is
doing to someone's natal placements. This answers questions about the sky
on its own: when a planet changed sign, when it turned retrograde, when it
last crossed a given degree, where it sat on some date in the past.

Everything here is a search over real positions, refined by bisection to
the moment of the crossing. Nothing is interpolated from a table of
published dates.
"""
from datetime import datetime, timedelta

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
         'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']

# Fastest each body travels, in degrees a day. The sampling step comes from
# this: coarse enough to be quick over decades, fine enough that nothing
# slips between two samples.
MAX_SPEED = {
    'Moon': 15.4, 'Mercury': 2.3, 'Venus': 1.3, 'Sun': 1.1, 'Mars': 0.9,
    'Jupiter': 0.25, 'Saturn': 0.14, 'Uranus': 0.07, 'Neptune': 0.05,
    'Pluto': 0.05, 'North Node': 0.25, 'South Node': 0.25
}

# Longest any of them stays retrograde, with room to spare. A search that
# starts mid-retrograde has to look back this far to find the station that
# began it.
LONGEST_RETROGRADE_DAYS = 200

# Enough samples for decades of a slow planet, few enough to stay quick
MAX_SAMPLES = 25000

# These never turn retrograde
ALWAYS_DIRECT = ['Sun', 'Moon']


class SkySearch:
    """Searches over a planet's own motion, with no chart involved"""

    def __init__(self, transit_calculator):
        self.tc = transit_calculator
        self.em = transit_calculator.em

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def step_days(self, planet):
        """
        How often to sample, so no sample-to-sample jump exceeds a degree.

        A degree is small against the 30° of a sign, which leaves room for
        the midpoint check to catch a planet that crosses a boundary and
        comes back between two samples.
        """
        return max(2.0 / 24.0, min(1.0 / MAX_SPEED.get(planet, 1.0), 10.0))

    def window(self, start_date, end_date, timezone):
        """The search window as Julian days, with the dates checked"""
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if end_dt <= start_dt:
            raise ValueError('end_date must be after start_date')
        return (self.em.get_julian_day_from_datetime(start_dt, timezone),
                self.em.get_julian_day_from_datetime(end_dt, timezone))

    def check_sample_count(self, planet, start_jd, end_jd):
        samples = (end_jd - start_jd) / self.step_days(planet)
        if samples > MAX_SAMPLES:
            years = (end_jd - start_jd) / 365.25
            raise ValueError(
                f'{years:.0f} years is too long a span to search for '
                f'{planet} at once. Try a shorter range: '
                f'{MAX_SAMPLES * self.step_days(planet) / 365.25:.0f} years '
                f'or less for this body.')

    def moment(self, jd, timezone):
        """A Julian day as the pieces every answer here reports"""
        when = self.em.get_datetime_from_julian_day(jd, timezone)
        return {
            'date': when.strftime('%Y-%m-%d'),
            'datetime': when.strftime('%Y-%m-%d %H:%M'),
            'time': when.strftime('%H:%M'),
            'timezone': self.tc.timezone_label(when.replace(tzinfo=None), timezone)
        }

    def describe_position(self, planet, jd, timezone='America/Los_Angeles'):
        """Where a planet is at one moment, in the terms a reading uses"""
        position = self.em.get_planet_position(planet, jd)
        longitude = position['longitude']
        moment = self.moment(jd, timezone)

        return {
            'planet': planet,
            **moment,
            'longitude': round(longitude, 6),
            'sign': self.tc.get_sign_from_longitude(longitude),
            'degree': int(longitude % 30),
            'minute': int(((longitude % 30) % 1) * 60),
            'position': self.format_position(longitude),
            'speed': round(position['speed'], 6),
            'retrograde': position['speed'] < 0
        }

    def format_position(self, longitude):
        """27°29' Libra"""
        within_sign = longitude % 30
        return (f"{int(within_sign)}°{int((within_sign % 1) * 60):02d}' "
                f"{self.tc.get_sign_from_longitude(longitude)}")

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def sky_on(self, date, time='12:00', timezone='America/Los_Angeles',
               planets=None):
        """Every planet's position at one moment"""
        jd = self.em.get_julian_day(date, time, timezone)
        bodies = planets or list(MAX_SPEED.keys())
        return [self.describe_position(planet, jd, timezone) for planet in bodies]

    def track(self, planet, start_date, end_date, samples=12,
              timezone='America/Los_Angeles'):
        """
        Where a planet has travelled across a span.

        Evenly spaced samples, with the ground it covered and the signs it
        passed through, so "where has Pluto been since 1990" has an answer
        that is not a wall of daily positions.
        """
        start_jd, end_jd = self.window(start_date, end_date, timezone)
        samples = max(2, min(int(samples), 200))
        step = (end_jd - start_jd) / (samples - 1)

        points = [self.describe_position(planet, start_jd + step * i, timezone)
                  for i in range(samples)]

        # Ground covered, following the planet rather than the zodiac: a
        # retrograde stretch takes longitude backwards, and the total has to
        # reflect that or a planet that ends where it started looks still.
        travelled = 0.0
        previous = points[0]['longitude']
        for point in points[1:]:
            travelled += abs(self.tc.signed_separation(point['longitude'], previous))
            previous = point['longitude']

        return {
            'planet': planet,
            'start_date': start_date,
            'end_date': end_date,
            'start': points[0],
            'end': points[-1],
            'samples': points,
            'degrees_travelled': round(travelled, 2),
            'signs_visited': self.signs_between(planet, start_date, end_date, timezone)
        }

    def signs_between(self, planet, start_date, end_date,
                      timezone='America/Los_Angeles'):
        """Every sign a planet occupied across a span, in order"""
        start_jd, end_jd = self.window(start_date, end_date, timezone)
        self.check_sample_count(planet, start_jd, end_jd)

        visited = [self.tc.get_sign_from_longitude(
            self.em.get_planet_position(planet, start_jd)['longitude'])]

        for crossing in self.find_ingresses(planet, start_jd, end_jd, timezone):
            if crossing['entered'] != visited[-1]:
                visited.append(crossing['entered'])
        return visited

    # ------------------------------------------------------------------
    # Sign changes
    # ------------------------------------------------------------------

    def ingresses(self, planet, start_date, end_date,
                  timezone='America/Los_Angeles'):
        """Every sign change in a window, retrograde re-entries included"""
        start_jd, end_jd = self.window(start_date, end_date, timezone)
        self.check_sample_count(planet, start_jd, end_jd)
        return self.find_ingresses(planet, start_jd, end_jd, timezone)

    def find_ingresses(self, planet, start_jd, end_jd, timezone):
        crossings = []
        step = self.step_days(planet)
        longitude_at = self.tc.position_lookup(planet)

        def sign_index(jd):
            return int(longitude_at(jd)['longitude'] / 30)

        def scan(jd_a, jd_b, sign_a, sign_b, depth=0):
            if sign_a != sign_b:
                # A boundary between the two. With a step this fine there is
                # only one, but a planet near a station can cross more than
                # one sign's worth of boundary in a long slow step.
                boundary = self.boundary_between(longitude_at, jd_a, jd_b)
                if boundary is None:
                    return
                crossings.append(self.describe_ingress(
                    planet, longitude_at, boundary, timezone))
                return

            if depth >= 3:
                return

            # Same sign at both ends does not mean it stayed there: a planet
            # can cross a boundary and station back over it between samples.
            mid_jd = (jd_a + jd_b) / 2
            sign_mid = sign_index(mid_jd)
            if sign_mid != sign_a:
                scan(jd_a, mid_jd, sign_a, sign_mid, depth + 1)
                scan(mid_jd, jd_b, sign_mid, sign_b, depth + 1)

        jd = start_jd
        sign_here = sign_index(jd)
        while jd < end_jd:
            next_jd = min(jd + step, end_jd)
            sign_next = sign_index(next_jd)
            scan(jd, next_jd, sign_here, sign_next)
            jd, sign_here = next_jd, sign_next

        return crossings

    def boundary_between(self, longitude_at, jd_a, jd_b):
        """
        Refine the moment a planet crossed a sign boundary.

        The boundary is whichever multiple of 30° lies between the two
        samples, found by bisecting on which side of it the planet is.
        """
        long_a = longitude_at(jd_a)['longitude']
        long_b = longitude_at(jd_b)['longitude']

        # Moving forward or back, the boundary crossed is the start of the
        # sign being entered (forwards) or left (backwards)
        sign_a, sign_b = int(long_a / 30), int(long_b / 30)
        forward = (sign_b - sign_a) % 12 == 1
        backward = (sign_a - sign_b) % 12 == 1
        if forward:
            boundary = (sign_b * 30.0) % 360
        elif backward:
            boundary = (sign_a * 30.0) % 360
        else:
            # More than one sign apart: the step was too coarse to say, and
            # a guess would invent a date
            return None

        low, high = jd_a, jd_b
        precision = 5.0 / 86400.0
        side_low = self.tc.signed_separation(long_a, boundary) < 0

        while (high - low) > precision:
            mid = (low + high) / 2
            side_mid = self.tc.signed_separation(
                longitude_at(mid)['longitude'], boundary) < 0
            if side_mid == side_low:
                low = mid
            else:
                high = mid

        return (low + high) / 2

    def describe_ingress(self, planet, longitude_at, jd, timezone):
        position = longitude_at(jd)
        retrograde = position['speed'] < 0
        # Right at the boundary the longitude can land either side of it, so
        # the signs are read a little before and a little after
        before = longitude_at(jd - 0.01)['longitude']
        after = longitude_at(jd + 0.01)['longitude']

        return {
            'planet': planet,
            **self.moment(jd, timezone),
            'left': self.tc.get_sign_from_longitude(before),
            'entered': self.tc.get_sign_from_longitude(after),
            'retrograde': retrograde,
            'direction': 'retrograde' if retrograde else 'direct'
        }

    def periods_in_sign(self, planet, sign, start_date, end_date,
                        timezone='America/Los_Angeles'):
        """
        Every stretch a planet spent in one sign inside a window.

        A planet that backs out and returns gets a stretch for each visit,
        which is the whole point of asking.
        """
        sign = self.normalize_sign(sign)
        start_jd, end_jd = self.window(start_date, end_date, timezone)
        self.check_sample_count(planet, start_jd, end_jd)

        longitude_at = self.tc.position_lookup(planet)
        in_sign = self.tc.get_sign_from_longitude(
            longitude_at(start_jd)['longitude']) == sign

        periods = []
        open_period = {'from': self.moment(start_jd, timezone),
                       'from_edge': 'before the search window'} if in_sign else None

        for crossing in self.find_ingresses(planet, start_jd, end_jd, timezone):
            if crossing['entered'] == sign and open_period is None:
                open_period = {'from': {k: crossing[k] for k in
                                        ('date', 'datetime', 'time', 'timezone')},
                               'from_edge': None,
                               'entered_retrograde': crossing['retrograde']}
            elif crossing['left'] == sign and open_period is not None:
                open_period['to'] = {k: crossing[k] for k in
                                     ('date', 'datetime', 'time', 'timezone')}
                open_period['to_edge'] = None
                open_period['left_retrograde'] = crossing['retrograde']
                periods.append(open_period)
                open_period = None

        if open_period is not None:
            open_period['to'] = self.moment(end_jd, timezone)
            open_period['to_edge'] = 'after the search window'
            periods.append(open_period)

        return {'planet': planet, 'sign': sign, 'periods': periods}

    def normalize_sign(self, sign):
        match = next((s for s in SIGNS if s.lower() == str(sign).strip().lower()), None)
        if not match:
            raise ValueError(f"'{sign}' is not a sign. One of: {', '.join(SIGNS)}")
        return match

    # ------------------------------------------------------------------
    # Stations and retrogrades
    # ------------------------------------------------------------------

    def stations(self, planet, start_date, end_date,
                 timezone='America/Los_Angeles'):
        """Every turn-around in a window, with where it happened"""
        if planet in ALWAYS_DIRECT:
            return []

        start_jd, end_jd = self.window(start_date, end_date, timezone)
        start_dt = self.em.get_datetime_from_julian_day(start_jd, timezone)
        end_dt = self.em.get_datetime_from_julian_day(end_jd, timezone)
        longitude_at = self.tc.position_lookup(planet)

        found = []
        for station in self.tc.find_stations(
                planet, start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None),
                timezone=timezone, step_hours=24):
            jd = self.em.get_julian_day_from_datetime(station['datetime'], timezone)
            longitude = longitude_at(jd)['longitude']
            found.append({
                'planet': planet,
                **self.moment(jd, timezone),
                'type': station['type'],
                'station': ('turns retrograde' if station['type'] == 'SR'
                            else 'turns direct'),
                'longitude': round(longitude, 6),
                'sign': self.tc.get_sign_from_longitude(longitude),
                'degree': int(longitude % 30),
                'minute': int(((longitude % 30) % 1) * 60),
                'position': self.format_position(longitude)
            })
        return found

    def retrograde_periods(self, planet, start_date, end_date,
                           timezone='America/Los_Angeles'):
        """
        Retrograde stretches overlapping a window, start and end paired.

        The search reaches back before the window, so a retrograde already
        under way on the first day is reported with the date it really
        began rather than the date the search started.
        """
        if planet in ALWAYS_DIRECT:
            return {'planet': planet, 'periods': [],
                    'note': f'{planet} never travels retrograde.'}

        reach_back = (datetime.strptime(start_date, '%Y-%m-%d')
                      - timedelta(days=LONGEST_RETROGRADE_DAYS)).strftime('%Y-%m-%d')
        stations = self.stations(planet, reach_back, end_date, timezone)

        periods = []
        open_period = None
        for station in stations:
            if station['type'] == 'SR':
                open_period = station
            elif open_period is not None:
                periods.append(self.pair_stations(open_period, station))
                open_period = None

        if open_period is not None:
            periods.append(self.pair_stations(open_period, None))

        # Only what actually touches the window the caller asked about
        return {
            'planet': planet,
            'periods': [p for p in periods
                        if (p['ends'] or {'date': '9999-12-31'})['date'] >= start_date]
        }

    def pair_stations(self, went_retrograde, turned_direct):
        period = {
            'begins': {k: went_retrograde[k] for k in
                       ('date', 'datetime', 'time', 'timezone', 'position', 'sign')},
            'ends': ({k: turned_direct[k] for k in
                      ('date', 'datetime', 'time', 'timezone', 'position', 'sign')}
                     if turned_direct else None)
        }
        if turned_direct:
            begin = datetime.strptime(went_retrograde['date'], '%Y-%m-%d')
            end = datetime.strptime(turned_direct['date'], '%Y-%m-%d')
            period['days'] = (end - begin).days
            period['travelled_back'] = round(abs(self.tc.signed_separation(
                turned_direct['longitude'], went_retrograde['longitude'])), 2)
        return period

    # ------------------------------------------------------------------
    # Degrees
    # ------------------------------------------------------------------

    def degree_crossings(self, planet, sign, degree, start_date, end_date,
                         aspect='Conjunction', timezone='America/Los_Angeles'):
        """
        Every time a planet reached a particular degree of the zodiac.

        With an aspect other than a conjunction, every time it reached an
        aspect to that degree, which is how a transit to a placement the app
        does not store gets answered.
        """
        from config import ALL_ASPECTS

        sign = self.normalize_sign(sign)
        if not 0 <= float(degree) < 30:
            raise ValueError('degree must be between 0 and 30')
        if aspect not in ALL_ASPECTS:
            raise ValueError(f"'{aspect}' is not an aspect. One of: "
                             f"{', '.join(ALL_ASPECTS)}")

        target = SIGNS.index(sign) * 30 + float(degree)
        start_jd, end_jd = self.window(start_date, end_date, timezone)
        self.check_sample_count(planet, start_jd, end_jd)

        start_dt = self.em.get_datetime_from_julian_day(start_jd, timezone)
        end_dt = self.em.get_datetime_from_julian_day(end_jd, timezone)
        _, _, step_hours, _ = self.tc.get_search_window(planet)

        hits = self.tc.find_exact_crossings(
            planet, target, ALL_ASPECTS[aspect]['angle'],
            start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None),
            step_hours=step_hours, timezone=timezone)

        return {
            'planet': planet,
            'aspect': aspect,
            'target': self.format_position(target),
            'crossings': [{
                'date': hit['datetime'].strftime('%Y-%m-%d'),
                'datetime': hit['datetime'].strftime('%Y-%m-%d %H:%M'),
                'time': hit['datetime'].strftime('%H:%M'),
                'timezone': self.tc.timezone_label(hit['datetime'], timezone),
                'retrograde': hit['retrograde'],
                'position': self.format_position(hit['longitude'])
                            if hit.get('longitude') is not None else None
            } for hit in hits]
        }
