"""
Transit Calculator
Core logic for calculating transits, aspects, and timelines
"""
from datetime import datetime, timedelta
import pytz
from ephemeris_manager import EphemerisManager
from natal_charts import NatalChartManager
from config import ASPECTS, PLANETS, CRITICAL_TRANSITS, HIGH_TRANSITS, MEDIUM_TRANSITS
import math

# An aspect counts as exact only at 0°00'. This tolerance (1 arc minute)
# is used for the rare case of a planet stationing right on the aspect point.
EXACT_TOLERANCE_DEG = 1.0 / 60.0

# The true lunar node wobbles direct/retrograde every few days. Those turns are
# real but tiny, so its direction is read over the surrounding week instead of
# from one day's speed - long enough that the wobble cannot outweigh the node's
# steady backwards drift.
OSCILLATING_POINTS = ['North Node', 'South Node']
PREVAILING_MOTION_DAYS = 10


class TransitCalculator:
    """Calculates transits and aspects"""

    def __init__(self):
        self.em = EphemerisManager()
        self.ncm = NatalChartManager()

        # Load or calculate natal charts
        if not self.ncm.load_charts_from_cache():
            print("Calculating natal charts...")
            self.ncm.calculate_all_charts()
            self.ncm.save_charts_to_cache()

    def get_transiting_positions(self, date_str, time_str='12:00', timezone='America/Los_Angeles'):
        """
        Get positions of all transiting planets for a given date and time

        Args:
            date_str: Date in format 'YYYY-MM-DD'
            time_str: Time in format 'HH:MM' (default: '12:00')
            timezone: Timezone string (default: 'America/Los_Angeles' for Pacific)

        Returns:
            Dictionary of planet positions
        """
        jd = self.em.get_julian_day(date_str, time_str, timezone)
        positions = {}

        for planet_name in PLANETS.keys():
            positions[planet_name] = self.em.get_planet_position(planet_name, jd)

        return positions

    def calculate_aspect_orb(self, transit_long, natal_long, aspect_angle):
        """
        Calculate the orb of an aspect

        Args:
            transit_long: Transiting planet longitude
            natal_long: Natal planet longitude
            aspect_angle: Ideal aspect angle (0, 60, 90, 120, 180)

        Returns:
            Orb in degrees (positive value)
        """
        # Calculate actual angle between planets
        diff = abs(transit_long - natal_long)
        if diff > 180:
            diff = 360 - diff

        # Calculate orb (difference from exact aspect)
        orb = abs(diff - aspect_angle)

        return orb

    def find_aspects(self, chart_key, date_str, max_orb=3, time_str='12:00', timezone='America/Los_Angeles'):
        """
        Find all active aspects for a given chart, date, and time

        Args:
            chart_key: Chart identifier ('christina', 'julian', 'davison')
            date_str: Date in format 'YYYY-MM-DD'
            max_orb: Maximum orb to consider (default 3°)
            time_str: Time in format 'HH:MM' (default: '12:00')
            timezone: Timezone string (default: 'America/Los_Angeles' for Pacific)

        Returns:
            List of active aspects
        """
        # Get transiting positions
        transit_positions = self.get_transiting_positions(date_str, time_str, timezone)

        # Get natal chart
        natal_chart = self.ncm.get_chart(chart_key)

        # Motion of each transiting planet: real positions a little before and
        # after now. Comparing positions instead of extrapolating from speed
        # keeps applying/separating correct through a station, where the listed
        # speed is nearly zero.
        base_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        motion = {}
        for planet_name in PLANETS.keys():
            step = timedelta(hours=1) if planet_name == 'Moon' else timedelta(hours=12)
            motion[planet_name] = {
                'future_longitude': self.get_longitude_at(planet_name, base_dt + step, timezone),
                'speed_before': self.get_position_at(planet_name, base_dt - step, timezone)['speed'],
                'speed_after': self.get_position_at(planet_name, base_dt + step, timezone)['speed'],
                'prevailing_retrograde': self.is_prevailing_retrograde(planet_name, base_dt, timezone)
            }

        aspects = []

        # Check each transiting planet
        for transit_planet in PLANETS.keys():
            transit_long = transit_positions[transit_planet]['longitude']
            transit_speed = transit_positions[transit_planet]['speed']

            # Retrograde straight from the ephemeris: negative speed = (Rx).
            # A planet is stationary when its direction differs on either side
            # of now, i.e. it turns around today.
            if transit_planet in OSCILLATING_POINTS:
                # Read over a week, so a two-day wobble is not called a station
                is_retrograde = motion[transit_planet]['prevailing_retrograde']
                is_stationary = False
            else:
                is_retrograde = transit_speed < 0
                is_stationary = ((motion[transit_planet]['speed_before'] < 0)
                                 != (motion[transit_planet]['speed_after'] < 0))

            # Which way it comes out of the station decides SR vs SD
            if is_stationary:
                station_type = 'SR' if motion[transit_planet]['speed_after'] < 0 else 'SD'
                motion_state = 'stationary retrograde' if station_type == 'SR' else 'stationary direct'
            else:
                station_type = None
                motion_state = 'retrograde' if is_retrograde else 'direct'

            # (Rx) while moving backwards, (SR)/(SD) on the day it turns
            marker = self.get_motion_marker({
                'station_type': station_type,
                'is_retrograde': is_retrograde
            }).strip()

            # Check against each natal planet and angle
            natal_points = list(PLANETS.keys()) + ['Ascendant', 'MC', 'Descendant', 'IC']

            for natal_point in natal_points:
                if natal_point not in natal_chart['positions']:
                    continue

                natal_long = natal_chart['positions'][natal_point]['longitude']

                # Check each aspect type
                for aspect_name, aspect_data in ASPECTS.items():
                    aspect_angle = aspect_data['angle']
                    aspect_orb = aspect_data['orb']

                    if aspect_orb > max_orb:
                        aspect_orb = max_orb

                    orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

                    if orb <= aspect_orb:
                        # Aspect is active!
                        # Applying or separating, from the planet's real motion.
                        # A planet that just turned retrograde is separating
                        # immediately, even if it was applying yesterday.
                        future_orb = self.calculate_aspect_orb(
                            motion[transit_planet]['future_longitude'], natal_long, aspect_angle
                        )
                        is_applying = future_orb < orb

                        # Calculate strength (100% at exact, 0% at max orb)
                        strength = (1 - (orb / aspect_orb)) * 100

                        # Get house position for transiting planet
                        transit_house = self.ncm.get_house_for_longitude(chart_key, transit_long)

                        aspects.append({
                            'transit_planet': transit_planet,
                            'natal_point': natal_point,
                            'aspect': aspect_name,
                            'aspect_symbol': aspect_data['symbol'],
                            'orb': orb,
                            'max_orb': aspect_orb,
                            'strength': strength,
                            'is_applying': is_applying,
                            'transit_longitude': transit_long,
                            'natal_longitude': natal_long,
                            'transit_speed': transit_speed,
                            'is_retrograde': is_retrograde,
                            'is_stationary': is_stationary,
                            'station_type': station_type,
                            'motion': motion_state,
                            'motion_marker': marker,
                            'transit_house': transit_house
                        })

        # Sort by orb (closest first)
        aspects.sort(key=lambda x: x['orb'])

        return aspects

    def is_aspect_applying(self, transit_long, natal_long, aspect_angle, transit_speed):
        """
        Determine if an aspect is applying or separating from a planet's speed

        Rough check for callers that already have a speed to hand. Near a
        station the speed is almost zero and this extrapolation gets shaky, so
        find_aspects compares real positions instead.

        Args:
            transit_long: Current transiting planet longitude
            natal_long: Natal planet longitude
            aspect_angle: Aspect angle (0, 60, 90, 120, 180)
            transit_speed: Speed of transiting planet (°/day)

        Returns:
            True if applying, False if separating
        """
        # Calculate current orb
        current_orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

        # Calculate position one day ahead
        future_long = (transit_long + transit_speed) % 360
        future_orb = self.calculate_aspect_orb(future_long, natal_long, aspect_angle)

        # If future orb is smaller, aspect is applying
        return future_orb < current_orb

    # ------------------------------------------------------------------
    # Exactness
    #
    # An aspect is EXACT only at the moment the transiting planet actually
    # crosses the aspect point (orb 0°00'). A planet that stations while it
    # is still applying never perfects the aspect - it simply turns around
    # and starts separating - so a station is never an exact date, no matter
    # how close the orb got.
    # ------------------------------------------------------------------

    def get_longitude_at(self, transit_planet, dt, timezone='America/Los_Angeles'):
        """Longitude of a transiting planet at a specific datetime"""
        jd = self.em.get_julian_day_from_datetime(dt, timezone)
        return self.em.get_planet_position(transit_planet, jd)['longitude']

    def get_position_at(self, transit_planet, dt, timezone='America/Los_Angeles'):
        """Full position (longitude + speed) of a transiting planet at a datetime"""
        jd = self.em.get_julian_day_from_datetime(dt, timezone)
        return self.em.get_planet_position(transit_planet, jd)

    def get_aspect_targets(self, natal_long, aspect_angle):
        """
        Longitudes where an aspect is exact.

        Conjunctions and oppositions have a single exact point; every other
        aspect has two (natal ± the aspect angle).
        """
        if aspect_angle == 0:
            return [natal_long % 360]
        if abs(aspect_angle - 180) < 1e-9:
            return [(natal_long + 180) % 360]
        return [(natal_long + aspect_angle) % 360, (natal_long - aspect_angle) % 360]

    def signed_separation(self, transit_long, target_long):
        """
        Signed distance from a transiting planet to an exact aspect point.

        Runs from -180 to +180 and is zero at perfection, so a change of sign
        between two samples means the planet really crossed the point.
        """
        return (transit_long - target_long + 180) % 360 - 180

    def _separation_at_jd(self, transit_planet, jd, target_long):
        """Signed separation from the aspect point at a Julian Day"""
        position = self.em.get_planet_position(transit_planet, jd)
        return self.signed_separation(position['longitude'], target_long)

    def _refine_crossing_jd(self, transit_planet, target_long, before_jd, after_jd):
        """Bisect a bracketed zero crossing down to a few seconds"""
        before_sep = self._separation_at_jd(transit_planet, before_jd, target_long)
        # Tight enough that even the Moon lands inside an arc second of exact
        precision = 5.0 / 86400.0

        while (after_jd - before_jd) > precision:
            mid_jd = (before_jd + after_jd) / 2
            mid_sep = self._separation_at_jd(transit_planet, mid_jd, target_long)

            if mid_sep == 0:
                return mid_jd

            if (mid_sep < 0) == (before_sep < 0):
                before_jd, before_sep = mid_jd, mid_sep
            else:
                after_jd = mid_jd

        return (before_jd + after_jd) / 2

    def is_prevailing_retrograde(self, transit_planet, dt, timezone='America/Los_Angeles',
                                 span_days=PREVAILING_MOTION_DAYS):
        """
        Direction of travel across the days either side of a moment.

        Used for the true node, whose speed flips back and forth every few days
        while its actual drift stays backwards.
        """
        before = self.get_longitude_at(transit_planet, dt - timedelta(days=span_days), timezone)
        after = self.get_longitude_at(transit_planet, dt + timedelta(days=span_days), timezone)

        return ((after - before + 180) % 360 - 180) < 0

    def get_search_window(self, transit_planet):
        """
        How far to look for a perfection, per planet speed.

        Far enough ahead that a retrograde detour still lands inside the
        window, sampled finely enough that no crossing slips between samples.

        Returns:
            Tuple (forward_span, backward_span, step_hours, show_time)
        """
        if transit_planet == 'Moon':
            return timedelta(days=45), timedelta(days=45), 2, True

        if transit_planet in ['Sun', 'Mercury', 'Venus', 'Mars']:
            return timedelta(days=400), timedelta(days=400), 12, True

        return timedelta(days=1095), timedelta(days=730), 24, False

    def find_exact_crossings(self, transit_planet, natal_long, aspect_angle,
                             start_dt, end_dt, step_hours=24,
                             timezone='America/Los_Angeles', max_results=None,
                             newest_first=False):
        """
        Find every moment an aspect actually perfects inside a window.

        Perfection is a zero crossing of the signed separation, never a minimum
        orb, so a planet that stations short of the aspect is correctly read as
        "never went exact". A planet that stations right on the aspect point
        (within EXACT_TOLERANCE_DEG) does count as exact.

        Args:
            transit_planet: Name of transiting planet
            natal_long: Longitude of the natal planet/point
            aspect_angle: Aspect angle (0, 60, 90, 120, 180)
            start_dt: Window start (datetime, read in timezone)
            end_dt: Window end (datetime, read in timezone)
            step_hours: Coarse sampling interval
            timezone: Timezone for the returned datetimes
            max_results: Stop after this many hits (per aspect point)
            newest_first: Scan backward from the end of the window, so
                          max_results returns the most recent hits

        Returns:
            List of dicts sorted by time:
            {'datetime': datetime, 'orb': float, 'retrograde': bool}
        """
        start_jd = self.em.get_julian_day_from_datetime(start_dt, timezone)
        end_jd = self.em.get_julian_day_from_datetime(end_dt, timezone)
        step = step_hours / 24.0

        # Scanning backward finds the most recent hit first, which is usually
        # only days away - much cheaper than sweeping the whole window.
        if newest_first:
            start_jd, end_jd, step = end_jd, start_jd, -step

        crossings = []

        for target_long in self.get_aspect_targets(natal_long, aspect_angle):

            def is_crossing(sep_a, sep_b):
                # Sign flip with both samples near the aspect point. The
                # nearness check skips the 180° wrap in signed_separation.
                return (sep_a < 0) != (sep_b < 0) and abs(sep_a) < 90 and abs(sep_b) < 90

            def record(bracket_a, bracket_b):
                before_jd, after_jd = sorted((bracket_a, bracket_b))
                hit_jd = self._refine_crossing_jd(transit_planet, target_long, before_jd, after_jd)
                position = self.em.get_planet_position(transit_planet, hit_jd)
                crossings.append({
                    'datetime': self.em.get_datetime_from_julian_day(hit_jd, timezone),
                    'orb': abs(self.signed_separation(position['longitude'], target_long)),
                    'retrograde': position['speed'] < 0
                })

            jd = start_jd
            sep = self._separation_at_jd(transit_planet, jd, target_long)

            # Track the turning point, for a planet that stations right on the
            # aspect point and so perfects without ever changing sign.
            closest_jd, closest_sep = jd, sep
            hits_here = 0

            def before_end(value):
                return value > end_jd if newest_first else value < end_jd

            def clamp(value):
                return max(value, end_jd) if newest_first else min(value, end_jd)

            def clamp_sub(value, limit):
                return max(value, limit) if newest_first else min(value, limit)

            while before_end(jd) and (max_results is None or hits_here < max_results):
                next_jd = clamp(jd + step)
                next_sep = self._separation_at_jd(transit_planet, next_jd, target_long)

                if abs(next_sep) < abs(closest_sep):
                    closest_jd, closest_sep = next_jd, next_sep

                travel = abs(next_sep - sep)

                if min(abs(sep), abs(next_sep)) < 2 * travel + 0.05:
                    # The aspect point is within reach of this step, so sample
                    # finely: a planet that stations just past exact crosses
                    # twice in quick succession and both hits are real.
                    sub_step = (next_jd - jd) / 8
                    sub_jd, sub_sep = jd, sep

                    while abs(next_jd - sub_jd) > 1e-9:
                        end_sub_jd = clamp_sub(sub_jd + sub_step, next_jd)
                        end_sub_sep = self._separation_at_jd(transit_planet, end_sub_jd, target_long)

                        if abs(end_sub_sep) < abs(closest_sep):
                            closest_jd, closest_sep = end_sub_jd, end_sub_sep

                        if is_crossing(sub_sep, end_sub_sep):
                            record(sub_jd, end_sub_jd)
                            hits_here += 1
                            if max_results is not None and hits_here >= max_results:
                                break

                        sub_jd, sub_sep = end_sub_jd, end_sub_sep

                elif is_crossing(sep, next_sep):
                    record(jd, next_jd)
                    hits_here += 1

                jd, sep = next_jd, next_sep

            # A planet that stations right on the aspect point perfects it
            # without ever changing sign. This only counts as exact when the
            # planet really turns around there - a planet that merely passed
            # the point just outside the window is not an exact hit.
            already_recorded = any(
                abs((c['datetime'] - self.em.get_datetime_from_julian_day(closest_jd, timezone)).total_seconds()) < 86400
                for c in crossings
            )

            if abs(closest_sep) <= EXACT_TOLERANCE_DEG and not already_recorded:
                speed_before = self.em.get_planet_position(transit_planet, closest_jd - 0.5)['speed']
                speed_after = self.em.get_planet_position(transit_planet, closest_jd + 0.5)['speed']

                if (speed_before < 0) != (speed_after < 0):
                    crossings.append({
                        'datetime': self.em.get_datetime_from_julian_day(closest_jd, timezone),
                        'orb': abs(closest_sep),
                        'retrograde': speed_after < 0
                    })

        crossings.sort(key=lambda c: c['datetime'])
        return crossings

    def find_closest_approach(self, transit_planet, natal_long, aspect_angle,
                              start_dt, end_dt, step_hours=24,
                              timezone='America/Los_Angeles'):
        """
        Tightest orb an aspect reaches in a window, and when.

        This is what an aspect that never perfects gets instead of an exact
        date: usually the moment the planet stations and turns back.

        Returns:
            Dict {'datetime': datetime, 'orb': float, 'is_station': bool}, or
            None if the window is empty.
        """
        start_jd = self.em.get_julian_day_from_datetime(start_dt, timezone)
        end_jd = self.em.get_julian_day_from_datetime(end_dt, timezone)
        step = step_hours / 24.0

        def orb_at(jd):
            position = self.em.get_planet_position(transit_planet, jd)
            return self.calculate_aspect_orb(position['longitude'], natal_long, aspect_angle)

        best_jd, best_orb = None, None
        jd = start_jd
        while jd <= end_jd:
            orb = orb_at(jd)
            if best_orb is None or orb < best_orb:
                best_jd, best_orb = jd, orb
            jd += step

        if best_jd is None:
            return None

        # Refine hour by hour around the coarse minimum
        hour = 1.0 / 24.0
        jd = max(best_jd - step, start_jd)
        refine_end = min(best_jd + step, end_jd)
        while jd <= refine_end:
            orb = orb_at(jd)
            if orb < best_orb:
                best_jd, best_orb = jd, orb
            jd += hour

        # A turning point is a station: direction differs on either side of it
        speed_before = self.em.get_planet_position(transit_planet, best_jd - 0.5)['speed']
        speed_after = self.em.get_planet_position(transit_planet, best_jd + 0.5)['speed']

        return {
            'datetime': self.em.get_datetime_from_julian_day(best_jd, timezone),
            'orb': best_orb,
            'is_station': (speed_before < 0) != (speed_after < 0)
        }

    def find_stations(self, transit_planet, start_dt, end_dt, timezone='America/Los_Angeles',
                      step_hours=24, natal_long=None, aspect_angle=None):
        """
        Every time a transiting planet turns around inside a window.

        A station is where the planet's speed changes sign. It is why an
        applying aspect can stop applying without ever reaching 0°00', and why
        a date range needs it called out: without a station in between, the
        planet keeps whatever direction it has on the dates shown.

        Args:
            natal_long, aspect_angle: optional, to also report the orb the
                                      aspect stands at when the planet stations

        Returns:
            List of dicts in time order:
            {'datetime': datetime, 'type': 'SR'|'SD', 'orb': float or None}
        """
        if end_dt <= start_dt:
            return []

        start_jd = self.em.get_julian_day_from_datetime(start_dt, timezone)
        end_jd = self.em.get_julian_day_from_datetime(end_dt, timezone)
        step = step_hours / 24.0

        def speed_at(jd):
            return self.em.get_planet_position(transit_planet, jd)['speed']

        stations = []
        jd = start_jd
        speed = speed_at(jd)

        while jd < end_jd:
            next_jd = min(jd + step, end_jd)
            next_speed = speed_at(next_jd)

            if (speed < 0) != (next_speed < 0):
                low, high = jd, next_jd
                while (high - low) > 30.0 / 86400.0:
                    mid = (low + high) / 2
                    if (speed_at(mid) < 0) == (speed < 0):
                        low = mid
                    else:
                        high = mid

                turn_jd = (low + high) / 2
                orb = None
                if natal_long is not None and aspect_angle is not None:
                    orb = self.calculate_aspect_orb(
                        self.em.get_planet_position(transit_planet, turn_jd)['longitude'],
                        natal_long, aspect_angle
                    )

                stations.append({
                    'datetime': self.em.get_datetime_from_julian_day(turn_jd, timezone),
                    'type': 'SR' if next_speed < 0 else 'SD',
                    'orb': orb
                })

            jd, speed = next_jd, next_speed

        if transit_planet in OSCILLATING_POINTS:
            # Keep only turns that change where the point is actually headed
            stations = [
                station for station in stations
                if self.is_prevailing_retrograde(transit_planet,
                                                 station['datetime'] - timedelta(days=1), timezone)
                != self.is_prevailing_retrograde(transit_planet,
                                                 station['datetime'] + timedelta(days=1), timezone)
            ]

        return stations

    def find_exact_aspect_date(self, chart_key, transit_planet, natal_point, aspect_name,
                               start_date, max_days=365, timezone='America/Los_Angeles'):
        """
        Find the next date an aspect actually goes exact (orb 0°00')

        Args:
            chart_key: Chart identifier
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect
            start_date: Date to start searching from (YYYY-MM-DD)
            max_days: Maximum days to search forward
            timezone: Timezone for the returned date

        Returns:
            Tuple of (date_str, orb), or (None, None) when the aspect never
            perfects in the window - for example when the transiting planet
            stations and turns retrograde before reaching the aspect point.
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        start = datetime.strptime(start_date, '%Y-%m-%d').replace(hour=12)
        crossings = self.find_exact_crossings(
            transit_planet, natal_long, aspect_angle,
            start, start + timedelta(days=max_days),
            step_hours=24, timezone=timezone, max_results=1
        )

        if not crossings:
            return None, None

        return crossings[0]['datetime'].strftime('%Y-%m-%d'), crossings[0]['orb']

    def find_exact_aspect_datetime(self, chart_key, transit_planet, natal_point, aspect_name,
                                    start_date, start_time='12:00', timezone='America/Los_Angeles',
                                    max_hours=168):
        """
        Find the next date AND time an aspect actually goes exact (orb 0°00')

        Args:
            chart_key: Chart identifier
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect
            start_date: Date to start searching from (YYYY-MM-DD)
            start_time: Time to start searching from (HH:MM)
            timezone: Timezone for calculations
            max_hours: Maximum hours to search forward (default 168 = 7 days)

        Returns:
            Tuple of (datetime_str, orb) in format 'YYYY-MM-DD HH:MM', or
            (None, None) when the aspect never perfects in the window.
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        # Sample finely enough that the Moon cannot skip past an aspect point
        fast_planets = ['Moon', 'Sun', 'Mercury', 'Venus', 'Mars']
        step_hours = 2 if transit_planet in fast_planets else 12

        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
        crossings = self.find_exact_crossings(
            transit_planet, natal_long, aspect_angle,
            start_dt, start_dt + timedelta(hours=max_hours),
            step_hours=step_hours, timezone=timezone, max_results=1
        )

        if not crossings:
            return None, None

        return crossings[0]['datetime'].strftime('%Y-%m-%d %H:%M'), crossings[0]['orb']

    def calculate_aspect_timeline(self, chart_key, transit_planet, natal_point,
                                  aspect_name, reference_date, precise=False):
        """
        Calculate complete timeline for an aspect (entry, exact, exit dates)

        Handles retrograde motion by finding the current transit window:
        - Searches backward from reference date to find when aspect entered orb
        - Searches forward from reference date to find when aspect exits orb
        - Finds exact dates within that window

        Args:
            chart_key: Chart identifier
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect
            reference_date: Reference date (YYYY-MM-DD)
            precise: If True, find exact times (hour/minute) for crossings

        Returns:
            Dictionary with timeline information
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        timeline = {
            'enter_5deg': None,
            'enter_3deg': None,
            'enter_1deg': None,
            'exact_dates': [],  # Every perfection in the window (retrogrades give 3)
            'exact_date': None,  # Nearest true perfection to reference
            'exact_datetime': None,
            'exact_orb': None,
            'perfects': False,  # False when the planet stations before going exact
            'closest_approach': None,  # Tightest orb reached when it never perfects
            'stations': [],  # Direction changes inside the window
            'leave_1deg': None,
            'leave_3deg': None,
            'leave_5deg': None
        }

        ref = datetime.strptime(reference_date, '%Y-%m-%d')

        def get_orb_for_datetime(dt):
            """Get orb for a specific datetime using Pacific time"""
            jd = self.em.get_julian_day(
                dt.strftime('%Y-%m-%d'),
                dt.strftime('%H:%M'),
                'America/Los_Angeles'
            )
            transit_pos = self.em.get_planet_position(transit_planet, jd)
            return self.calculate_aspect_orb(transit_pos['longitude'], natal_long, aspect_angle)

        def get_orb_for_date(date):
            """Get orb at noon Pacific time for a given date"""
            dt = datetime.combine(date.date() if hasattr(date, 'date') else date, datetime.min.time().replace(hour=12))
            return get_orb_for_datetime(dt)

        def find_precise_crossing(known_date_str, threshold, crossing_type='exit'):
            """
            Refine a known crossing date to hour:minute precision.

            Args:
                known_date_str: Already-known date of crossing (YYYY-MM-DD)
                threshold: Orb threshold (1, 3, or 5 degrees)
                crossing_type: 'entry' (orb decreasing past threshold) or 'exit' (orb increasing past threshold)

            Returns:
                Datetime string with time (YYYY-MM-DD HH:MM) or original date
            """
            if not known_date_str:
                return None

            # Parse the known date
            known_date = datetime.strptime(known_date_str, '%Y-%m-%d')

            # Search hour by hour across the day (and day before/after for edge cases)
            search_start = datetime.combine(known_date.date(), datetime.min.time()) - timedelta(hours=12)

            prev_orb = get_orb_for_datetime(search_start)
            for hour in range(48):  # Check 48 hours centered on the known date
                check_time = search_start + timedelta(hours=hour)
                orb = get_orb_for_datetime(check_time)

                crossed = False
                if crossing_type == 'exit':
                    crossed = orb > threshold and prev_orb <= threshold
                else:
                    crossed = orb <= threshold and prev_orb > threshold

                if crossed:
                    # Refine to minute precision using binary search
                    low = check_time - timedelta(hours=1)
                    high = check_time

                    for _ in range(6):  # ~1 minute precision after 6 iterations
                        mid = low + (high - low) / 2
                        mid_orb = get_orb_for_datetime(mid)

                        if crossing_type == 'exit':
                            if mid_orb > threshold:
                                high = mid
                            else:
                                low = mid
                        else:
                            if mid_orb <= threshold:
                                high = mid
                            else:
                                low = mid

                    return high.strftime('%Y-%m-%d %H:%M')
                prev_orb = orb

            # Fallback to noon on the known date
            return known_date_str + ' 12:00'

        # Step 1: Find the current transit window boundaries (5° orb)
        # Search backward from reference date to find when we entered 5° orb
        prev_orb = get_orb_for_date(ref)
        for days_back in range(1, 400):
            check_date = ref - timedelta(days=days_back)
            orb = get_orb_for_date(check_date)

            # Found where orb crossed from >5 to <=5 (we entered)
            if orb > 5 and prev_orb <= 5:
                timeline['enter_5deg'] = (check_date + timedelta(days=1)).strftime('%Y-%m-%d')
                break
            prev_orb = orb

        # Search forward from reference date to find when we exit 5° orb
        prev_orb = get_orb_for_date(ref)
        for days_forward in range(1, 400):
            check_date = ref + timedelta(days=days_forward)
            orb = get_orb_for_date(check_date)

            # Found where orb crossed from <=5 to >5 (we're leaving)
            if orb > 5 and prev_orb <= 5:
                timeline['leave_5deg'] = check_date.strftime('%Y-%m-%d')
                break
            prev_orb = orb

        # Step 2: Within the window, find 3° entry/exit (nearest to reference date)
        # Search backward for most recent 3° entry
        prev_orb = get_orb_for_date(ref)
        for days_back in range(1, 400):
            check_date = ref - timedelta(days=days_back)
            orb = get_orb_for_date(check_date)

            if orb > 3 and prev_orb <= 3:
                timeline['enter_3deg'] = (check_date + timedelta(days=1)).strftime('%Y-%m-%d')
                break
            # Stop if we've left the 5° window
            if orb > 5:
                break
            prev_orb = orb

        # Search forward for next 3° exit
        prev_orb = get_orb_for_date(ref)
        for days_forward in range(1, 400):
            check_date = ref + timedelta(days=days_forward)
            orb = get_orb_for_date(check_date)

            if orb > 3 and prev_orb <= 3:
                timeline['leave_3deg'] = check_date.strftime('%Y-%m-%d')
                break
            if orb > 5:
                break
            prev_orb = orb

        # Step 3: Within 3° window, find 1° entry/exit
        # Search backward for most recent 1° entry
        prev_orb = get_orb_for_date(ref)
        for days_back in range(1, 200):
            check_date = ref - timedelta(days=days_back)
            orb = get_orb_for_date(check_date)

            if orb > 1 and prev_orb <= 1:
                timeline['enter_1deg'] = (check_date + timedelta(days=1)).strftime('%Y-%m-%d')
                break
            if orb > 3:
                break
            prev_orb = orb

        # Search forward for next 1° exit
        prev_orb = get_orb_for_date(ref)
        for days_forward in range(1, 200):
            check_date = ref + timedelta(days=days_forward)
            orb = get_orb_for_date(check_date)

            if orb > 1 and prev_orb <= 1:
                timeline['leave_1deg'] = check_date.strftime('%Y-%m-%d')
                break
            if orb > 3:
                break
            prev_orb = orb

        # Step 4: Find every real perfection around the reference date
        # Only a true 0°00' crossing counts - a planet that stations short of
        # the aspect flips to separating without ever going exact.
        forward_span, back_span, step_hours, _ = self.get_search_window(transit_planet)
        window_start = ref - back_span
        window_end = ref + forward_span
        crossings = self.find_exact_crossings(
            transit_planet, natal_long, aspect_angle,
            window_start, window_end, step_hours=step_hours
        )

        # Direction changes inside the window being reported - the transit's
        # own orb window, stretched to cover a perfection that lands outside
        # it. With none listed, the planet holds one direction throughout.
        def parse_timeline_date(value, fallback):
            return datetime.strptime(value[:10], '%Y-%m-%d') if value else fallback

        stations_from = parse_timeline_date(timeline['enter_5deg'], ref)
        stations_to = parse_timeline_date(timeline['leave_5deg'], ref)
        if crossings:
            stations_to = max(stations_to, max(c['datetime'] for c in crossings))
            stations_from = min(stations_from, min(c['datetime'] for c in crossings))
        stations_to = max(stations_to, ref)
        stations_from = min(stations_from, ref)

        timeline['stations'] = [
            {
                'date': station['datetime'].strftime('%Y-%m-%d'),
                'datetime': station['datetime'].strftime('%Y-%m-%d %H:%M'),
                'type': station['type'],
                'orb': station['orb']
            }
            for station in self.find_stations(
                transit_planet, stations_from, stations_to,
                natal_long=natal_long, aspect_angle=aspect_angle
            )
        ]

        timeline['exact_dates'] = [
            {
                'date': c['datetime'].strftime('%Y-%m-%d'),
                'datetime': c['datetime'].strftime('%Y-%m-%d %H:%M'),
                'orb': c['orb'],
                'retrograde': c['retrograde']
            }
            for c in crossings
        ]

        if crossings:
            nearest = min(crossings, key=lambda c: abs(c['datetime'] - ref))
            timeline['perfects'] = True
            timeline['exact_date'] = nearest['datetime'].strftime('%Y-%m-%d')
            timeline['exact_datetime'] = nearest['datetime'].strftime('%Y-%m-%d %H:%M')
            timeline['exact_orb'] = nearest['orb']
            timeline['exact_retrograde'] = nearest['retrograde']
        else:
            # Never goes exact in this window - report how close it gets instead
            closest = self.find_closest_approach(
                transit_planet, natal_long, aspect_angle, window_start, window_end
            )
            if closest:
                timeline['closest_approach'] = {
                    'date': closest['datetime'].strftime('%Y-%m-%d'),
                    'datetime': closest['datetime'].strftime('%Y-%m-%d %H:%M'),
                    'orb': closest['orb'],
                    'is_station': closest['is_station']
                }

        # Step 5: If precise mode, find exact times for all crossings
        if precise:
            # Find precise entry times (pass the already-known date string)
            if timeline['enter_5deg']:
                precise_time = find_precise_crossing(timeline['enter_5deg'], 5, 'entry')
                if precise_time:
                    timeline['enter_5deg'] = precise_time

            if timeline['enter_3deg']:
                precise_time = find_precise_crossing(timeline['enter_3deg'], 3, 'entry')
                if precise_time:
                    timeline['enter_3deg'] = precise_time

            if timeline['enter_1deg']:
                precise_time = find_precise_crossing(timeline['enter_1deg'], 1, 'entry')
                if precise_time:
                    timeline['enter_1deg'] = precise_time

            # Find precise exit times
            if timeline['leave_1deg']:
                precise_time = find_precise_crossing(timeline['leave_1deg'], 1, 'exit')
                if precise_time:
                    timeline['leave_1deg'] = precise_time

            if timeline['leave_3deg']:
                precise_time = find_precise_crossing(timeline['leave_3deg'], 3, 'exit')
                if precise_time:
                    timeline['leave_3deg'] = precise_time

            if timeline['leave_5deg']:
                precise_time = find_precise_crossing(timeline['leave_5deg'], 5, 'exit')
                if precise_time:
                    timeline['leave_5deg'] = precise_time

        return timeline

    def summarize_transit_window(self, chart_key, transit_planet, natal_point, aspect_name,
                                 reference_date, timezone='America/Los_Angeles', orb=3.0,
                                 max_days=400):
        """
        What a journal needs about one transit, without the full timeline.

        The orb window around the reference date, every perfection inside it,
        the stations inside it, and - when the planet stations short and never
        perfects there - the next date it actually does. Searching only the orb
        window (rather than years either side) keeps a multi-chart journal fast.

        Returns:
            Dict with enter, leave, passes, stations, next_exact_after_window
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)
        ref = datetime.strptime(reference_date[:10], '%Y-%m-%d').replace(hour=12)

        def orb_on(day_offset):
            jd = self.em.get_julian_day_from_datetime(ref + timedelta(days=day_offset), timezone)
            position = self.em.get_planet_position(transit_planet, jd)
            return self.calculate_aspect_orb(position['longitude'], natal_long, aspect_angle)

        def edge(direction):
            """Days until the aspect leaves orb, scanning coarsely then to the day"""
            coarse = 5
            offset = 0
            while offset < max_days:
                offset += coarse
                if orb_on(direction * offset) > orb:
                    for step_back in range(1, coarse + 1):
                        if orb_on(direction * (offset - step_back)) <= orb:
                            return offset - step_back
                    return offset
            return None

        days_before = edge(-1)
        days_after = edge(1)

        window_start = ref - timedelta(days=days_before if days_before is not None else max_days)
        window_end = ref + timedelta(days=days_after if days_after is not None else max_days)

        step_hours = 2 if transit_planet == 'Moon' else (12 if transit_planet in
                                                         ['Sun', 'Mercury', 'Venus', 'Mars'] else 24)

        passes = self.find_exact_crossings(
            transit_planet, natal_long, aspect_angle,
            window_start, window_end, step_hours=step_hours, timezone=timezone
        )

        stations = self.find_stations(
            transit_planet, window_start, window_end, timezone=timezone,
            step_hours=min(step_hours, 24), natal_long=natal_long, aspect_angle=aspect_angle
        )

        # Stationed short of the aspect: say where it finally perfects
        next_after = None
        if not passes:
            forward_span, _, look_ahead_step, _ = self.get_search_window(transit_planet)
            later = self.find_exact_crossings(
                transit_planet, natal_long, aspect_angle,
                window_end, window_end + forward_span,
                step_hours=look_ahead_step, timezone=timezone, max_results=1
            )
            if later:
                next_after = {
                    'date': later[0]['datetime'].strftime('%Y-%m-%d'),
                    'retrograde': later[0]['retrograde']
                }

        return {
            'enter': window_start.strftime('%Y-%m-%d') if days_before is not None else None,
            'leave': window_end.strftime('%Y-%m-%d') if days_after is not None else None,
            'passes': [
                {'date': hit['datetime'].strftime('%Y-%m-%d'), 'retrograde': hit['retrograde']}
                for hit in passes
            ],
            'stations': [
                {'date': station['datetime'].strftime('%Y-%m-%d'),
                 'type': station['type'], 'orb': station['orb']}
                for station in stations
            ],
            'next_exact_after_window': next_after
        }

    def rate_aspect_significance(self, transit_planet, natal_point, aspect_name):
        """
        Rate the significance of an aspect

        Args:
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect

        Returns:
            Tuple: (significance_level, is_challenging)
        """
        # Determine if aspect is challenging based on aspect type AND planet
        is_challenging = self.is_aspect_challenging(transit_planet, aspect_name)

        # Check if it's a critical transit
        for t_planet, n_points in CRITICAL_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                return ('CRITICAL', is_challenging)

        # Check if it's a high significance transit
        for t_planet, n_points in HIGH_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                return ('HIGH', is_challenging)

        # Check if it's a medium significance transit
        for t_planet, n_points in MEDIUM_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                return ('MEDIUM', is_challenging)

        # Default to low significance
        return ('LOW', is_challenging)

    def is_aspect_challenging(self, transit_planet, aspect_name):
        """
        Determine if an aspect is challenging based on planet and aspect type

        Rules:
        - Squares and Oppositions are always challenging
        - Sextiles and Trines are always supportive
        - Conjunctions depend on the transiting planet:
            SUPPORTIVE: Venus, Jupiter, North Node
            CHALLENGING: Saturn, Pluto, South Node, Mars
            TRANSFORMATIVE (challenging): Uranus, Neptune
            NEUTRAL: Sun, Moon, Mercury (depends on context, default supportive)
        """
        # Squares and Oppositions are always challenging
        if aspect_name in ['Square', 'Opposition']:
            return True

        # Sextiles and Trines are always supportive
        if aspect_name in ['Sextile', 'Trine']:
            return False

        # Conjunctions depend on the planet
        if aspect_name == 'Conjunction':
            # Supportive conjunctions
            if transit_planet in ['Venus', 'Jupiter', 'North Node']:
                return False

            # Challenging conjunctions
            if transit_planet in ['Saturn', 'Pluto', 'South Node', 'Mars']:
                return True

            # Transformative (treat as challenging - can go either way but often intense)
            if transit_planet in ['Uranus', 'Neptune']:
                return True

            # Neutral planets (Sun, Moon, Mercury) - default to supportive
            return False

        # Default
        return False

    def get_sign_from_longitude(self, longitude):
        """Get zodiac sign name from longitude"""
        signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        return signs[int(longitude / 30)]

    def get_aspect_word(self, aspect_name):
        """Get the word form of an aspect for text output"""
        aspect_words = {
            'Conjunction': 'conjunct',
            'Sextile': 'sextile',
            'Square': 'square',
            'Trine': 'trine',
            'Opposition': 'opposite'
        }
        return aspect_words.get(aspect_name, aspect_name.lower())

    def format_orb(self, orb):
        """Format an orb in degrees and arc minutes (e.g. 1°23')"""
        total_minutes = round(orb * 60)
        return f"{total_minutes // 60}°{total_minutes % 60:02d}'"

    def format_exactness(self, aspect):
        """
        Text for when an aspect perfects.

        Exact is the moment the aspect reaches 0°00' and nothing else. Applying
        or separating and "does it perfect again?" are separate questions: an
        aspect can be separating now and still have another exact pass coming,
        because the planet stations and travels back over the same point. Both
        the pass behind and the pass ahead are reported, with the station in
        between that turns the planet around. A hit made while the planet is
        retrograde is marked (Rx); unmarked means direct.
        """
        # Times of day are only meaningful for the fast movers
        with_time = aspect['transit_planet'] in ['Moon', 'Sun', 'Mercury', 'Venus', 'Mars']

        def format_hit(hit, label):
            hit_dt = datetime.strptime(hit['datetime'], '%Y-%m-%d %H:%M')
            text = f" | {label} {hit_dt.strftime('%m-%d-%Y')}"
            if with_time:
                text += f" ~{self.format_time_12hr(hit_dt.strftime('%H:%M'))} {self.timezone_label(hit_dt)}"
            if hit.get('retrograde'):
                text += ' (Rx)'
            return text

        def format_stations():
            # Direction changes between now and the next perfection. With none
            # listed, the planet keeps the direction it has today.
            stations = aspect.get('stations') or []
            if not stations:
                return ''
            # The true node wobbles every few days; cap rather than bury the line
            shown = stations[:3]
            marks = ', '.join(
                ('goes Rx ' if station['type'] == 'SR' else 'stations direct ')
                + datetime.strptime(station['date'], '%Y-%m-%d').strftime('%m-%d-%Y')
                for station in shown
            )
            if len(stations) > len(shown):
                marks += f", +{len(stations) - len(shown)} more"
            return f" ({marks})"

        previous_exact = aspect.get('previous_exact') or aspect.get('last_exact')
        next_exact = aspect.get('next_exact') or ({
            'datetime': aspect.get('exact_datetime') or (aspect['exact_date'] + ' 12:00'),
            'retrograde': aspect.get('exact_retrograde')
        } if aspect.get('exact_date') else None)

        # See show_next_exact / show_previous_exact for which passes are worth
        # quoting; older callers fall back to whichever one exists
        show_next = aspect.get('show_next_exact')
        if show_next is None:
            show_next = bool(next_exact) and (aspect['is_applying'] or not previous_exact)

        show_previous = aspect.get('show_previous_exact')
        if show_previous is None:
            show_previous = bool(previous_exact) and not aspect['is_applying']

        parts = ''

        if previous_exact and show_previous:
            parts += format_hit(previous_exact, 'Was exact')
            if aspect.get('final_pass'):
                parts += ' (final pass)'

        if next_exact and show_next:
            parts += format_hit(next_exact, 'Next exact' if parts else 'Exact')

        if not parts:
            return ' | No exact hit in range'

        # The stations explain the return pass, so they go with it
        return parts + (format_stations() if (next_exact and show_next) else '')

    def get_motion_marker(self, aspect):
        """
        Retrograde marker for a transiting planet.

        '(Rx)' while the planet is moving backwards, '(SR)'/'(SD)' on the day
        it actually stations (turns retrograde / turns direct).
        """
        if aspect.get('station_type'):
            return f" ({aspect['station_type']})"
        if aspect.get('is_retrograde'):
            return ' (Rx)'
        return ''

    def timezone_label(self, when, timezone='America/Los_Angeles'):
        """
        'PDT' or 'PST' for a given moment.

        Everything here runs on Pacific time, which is daylight time from March
        to November - labelling it PST year round is wrong for most of the year.
        """
        if isinstance(when, str):
            when = datetime.strptime(when[:16], '%Y-%m-%d %H:%M') if len(when) > 10 \
                else datetime.strptime(when[:10], '%Y-%m-%d')

        return pytz.timezone(timezone).localize(when).tzname()

    def format_time_12hr(self, time_24hr):
        """Convert 24-hour time to 12-hour format with am/pm"""
        try:
            dt = datetime.strptime(time_24hr, '%H:%M')
            return dt.strftime('%I:%M%p').lstrip('0').lower()
        except:
            return time_24hr

    def get_daily_dashboard(self, chart_key, date_str, max_orb=3, time_str='12:00', timezone='America/Los_Angeles'):
        """
        Get complete daily dashboard for a chart

        Args:
            chart_key: Chart identifier
            date_str: Date in format 'YYYY-MM-DD'
            max_orb: Maximum orb to consider
            time_str: Time in format 'HH:MM' (default: '12:00')
            timezone: Timezone string (default: 'America/Los_Angeles' for Pacific)

        Returns:
            Dictionary with all aspects and metadata
        """
        aspects = self.find_aspects(chart_key, date_str, max_orb, time_str, timezone)

        # Add significance ratings
        for aspect in aspects:
            significance, is_challenging = self.rate_aspect_significance(
                aspect['transit_planet'],
                aspect['natal_point'],
                aspect['aspect']
            )
            aspect['significance'] = significance
            aspect['is_challenging'] = is_challenging

        # Find the real perfections (orb 0°00') around each aspect: the last
        # one behind us and the next one ahead. Exactness is the 0°00' crossing
        # and nothing else - a planet stationing and flipping from applying to
        # separating is not an exact hit, however tight the orb got.
        base_dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')

        for aspect in aspects:
            transit_planet = aspect['transit_planet']
            natal_long = aspect['natal_longitude']
            aspect_angle = ASPECTS[aspect['aspect']]['angle']

            # Times of day are only meaningful for the fast movers
            forward_span, back_span, step_hours, show_time = self.get_search_window(transit_planet)

            next_hits = self.find_exact_crossings(
                transit_planet, natal_long, aspect_angle,
                base_dt, base_dt + forward_span,
                step_hours=step_hours, timezone=timezone, max_results=1
            )
            past_hits = self.find_exact_crossings(
                transit_planet, natal_long, aspect_angle,
                base_dt - back_span, base_dt,
                step_hours=step_hours, timezone=timezone,
                max_results=1, newest_first=True
            )

            def describe(hit):
                return {
                    'date': hit['datetime'].strftime('%Y-%m-%d'),
                    'datetime': hit['datetime'].strftime('%Y-%m-%d %H:%M'),
                    'orb': hit['orb'],
                    'retrograde': hit['retrograde']
                }

            aspect['last_exact'] = describe(past_hits[-1]) if past_hits else None

            aspect['perfects'] = bool(next_hits)

            if next_hits:
                hit = describe(next_hits[0])
                aspect['exact_date'] = hit['date']
                aspect['exact_datetime'] = hit['datetime'] if show_time else None
                aspect['exact_orb'] = hit['orb']
                aspect['exact_retrograde'] = hit['retrograde']
            else:
                aspect['exact_date'] = None
                aspect['exact_datetime'] = None
                aspect['exact_orb'] = None
                aspect['exact_retrograde'] = None

            # Applying/separating and "does it perfect again?" are separate
            # questions: an aspect can be separating right now and still have
            # another exact pass coming once the planet stations and reverses
            # back over the point. So both perfections are reported.
            aspect['previous_exact'] = aspect['last_exact']
            aspect['next_exact'] = describe(next_hits[0]) if next_hits else None

            # A slow planet with a hit behind it and nothing ahead in a
            # three-year search has finished with this aspect for good
            aspect['final_pass'] = bool(
                aspect['previous_exact'] and not aspect['next_exact'] and not show_time
            )

            # Direction changes between now and the next perfection - the
            # station is what turns the planet back over the point.
            if aspect['next_exact']:
                span_start = base_dt
                span_end = datetime.strptime(aspect['next_exact']['datetime'], '%Y-%m-%d %H:%M')
            else:
                # Nothing ahead to turn back toward, so no station to call out
                span_start, span_end = base_dt, base_dt

            aspect['stations'] = [
                {
                    'date': station['datetime'].strftime('%Y-%m-%d'),
                    'datetime': station['datetime'].strftime('%Y-%m-%d %H:%M'),
                    'type': station['type'],
                    'orb': station['orb']
                }
                for station in self.find_stations(
                    transit_planet, span_start, span_end,
                    timezone=timezone, step_hours=min(step_hours, 24),
                    natal_long=natal_long, aspect_angle=aspect_angle
                )
            ]

            # What to quote. An applying aspect is heading for its next
            # perfection, so that always leads. Once an aspect has perfected,
            # the next pass is only worth quoting for a slow planet coming back
            # over the point - within six months, or with a station in between
            # to turn it around. A fast planet's next pass is just its cycle.
            if aspect['next_exact']:
                next_dt = datetime.strptime(aspect['next_exact']['datetime'], '%Y-%m-%d %H:%M')
                aspect['show_next_exact'] = (
                    aspect['is_applying']
                    or not aspect['previous_exact']
                    or (not show_time
                        and (next_dt <= base_dt + timedelta(days=183) or bool(aspect['stations'])))
                )
            else:
                aspect['show_next_exact'] = False

            # The pass behind us is worth quoting when the aspect is separating
            # from it, or when a slow planet stationed since - that station is
            # what makes this the same retrograde series rather than old news.
            if aspect['previous_exact'] and aspect['is_applying']:
                previous_dt = datetime.strptime(aspect['previous_exact']['datetime'], '%Y-%m-%d %H:%M')
                aspect['show_previous_exact'] = bool(
                    not show_time
                    and self.find_stations(transit_planet, previous_dt, base_dt,
                                           timezone=timezone, step_hours=min(step_hours, 24))
                )
            else:
                aspect['show_previous_exact'] = bool(aspect['previous_exact'])

            # Ready-made copy for the UI, so the app and the copy/paste text
            # always describe exactness the same way
            aspect['exact_summary'] = self.format_exactness(aspect).lstrip(' |').strip()

            # Add sign information for plain text output
            aspect['transit_sign'] = self.get_sign_from_longitude(aspect['transit_longitude'])
            aspect['natal_sign'] = self.get_sign_from_longitude(aspect['natal_longitude'])

        # Generate plain text list
        plain_text_lines = self.generate_plain_text_list(chart_key, date_str, time_str, aspects, timezone)

        chart_name, chart_short_name = self.get_chart_names(chart_key)

        return {
            'chart': chart_key,
            # Full name for headings and copy/paste, short one for inline use.
            # The chart picker keeps its own short label.
            'chart_name': chart_name,
            'chart_short_name': chart_short_name,
            'date': date_str,
            'time': time_str,
            'timezone': timezone,
            'total_aspects': len(aspects),
            'aspects': aspects,
            'plain_text': plain_text_lines
        }

    def get_chart_names(self, chart_key):
        """
        Full chart name for headings, short name for inline use

        The Davison chart's full label is a sentence, which reads badly in the
        middle of every aspect line.
        """
        chart = self.ncm.get_chart(chart_key)
        return chart['name'], chart.get('short_name', chart['name'])

    def generate_plain_text_list(self, chart_key, date_str, time_str, aspects, timezone='America/Los_Angeles'):
        """Generate a plain text list of aspects for easy copying"""
        chart_name, chart_short_name = self.get_chart_names(chart_key)
        time_12hr = self.format_time_12hr(time_str)

        # Format the date nicely
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        date_formatted = dt.strftime('%B %d, %Y')

        zone = self.timezone_label(f"{date_str} {time_str}", timezone)

        lines = [f"{date_formatted} Transits at {time_12hr} {zone}", f"for {chart_name}", ""]

        # Add current planetary positions section
        jd = self.em.get_julian_day(date_str, time_str, timezone)
        lines.append("==================================================")
        lines.append(f"WHERE THE PLANETS ARE IN THE SKY AT {time_12hr} {zone}")
        lines.append("==================================================")
        lines.append("")

        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
                       'Saturn', 'Uranus', 'Neptune', 'Pluto',
                       'North Node', 'South Node']
        for planet in planet_order:
            pos = self.em.get_planet_position(planet, jd)
            sign = self.get_sign_from_longitude(pos['longitude'])
            degree = int(pos['longitude'] % 30)
            lines.append(f"  {planet:12} - {degree}° {sign}")
        lines.append("")

        # Add natal placements section
        chart = self.ncm.get_chart(chart_key)
        lines.append("==================================================")
        lines.append(f"{chart_name.upper()}'S NATAL PLACEMENTS")
        lines.append("==================================================")
        lines.append("")

        natal_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
                       'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron',
                       'North Node', 'South Node', 'Ascendant', 'Midheaven']
        for point in natal_order:
            if point in chart['positions']:
                longitude = chart['positions'][point]['longitude']
                sign = self.get_sign_from_longitude(longitude)
                degree = int(longitude % 30)
                lines.append(f"  {point:12} - {degree}° {sign}")
        lines.append("")

        # Add Moon transits section
        lines.append("==================================================")
        lines.append(f"MOON TRANSITS HAPPENING FOR {chart_name.upper()} TODAY")
        lines.append("==================================================")
        lines.append("")

        moon_info = self._get_moon_daily_info(chart_key, date_str, timezone)
        moon_line = f"Moon in {moon_info['sign']} (House {moon_info['house']})"
        if moon_info['end_sign']:
            moon_line += f", enters {moon_info['end_sign']}"
        lines.append(moon_line)

        if moon_info['aspects']:
            for asp in moon_info['aspects']:
                if asp.get('sign_change'):
                    lines.append(f"  {asp['time_12hr']:8} Moon enters {asp['sign_change']}")
                elif asp['natal_point']:
                    lines.append(f"  {asp['time_12hr']:8} Moon {asp['aspect_word']} {chart_name}'s natal {asp['natal_point']}")

        lines.append("")

        # Add planetary transits section
        lines.append("==================================================")
        lines.append(f"PLANETARY TRANSITS TO {chart_name.upper()}'S NATAL PLACEMENTS")
        lines.append("==================================================")
        lines.append("")

        for aspect in aspects:
            # Skip Moon aspects in main list since we show them above
            if aspect['transit_planet'] == 'Moon':
                continue

            direction = "applying" if aspect['is_applying'] else "separating"
            orb_str = self.format_orb(aspect['orb'])

            # Build the aspect description
            transit_planet = aspect['transit_planet']
            transit_sign = aspect['transit_sign']
            aspect_word = self.get_aspect_word(aspect['aspect'])
            natal_point = aspect['natal_point']
            natal_sign = aspect['natal_sign']

            # (Rx) for retrograde, (SR)/(SD) on the day the planet stations
            motion_mark = self.get_motion_marker(aspect)

            line = (f"{transit_planet}{motion_mark} in {transit_sign} {aspect_word} "
                    f"{chart_short_name}'s natal {natal_point} in {natal_sign} at {orb_str} {direction}")

            # Exact means the aspect really reaches 0°00'. A planet that
            # stations before then never goes exact, so say that instead.
            line += self.format_exactness(aspect)

            lines.append(line)

        return "\n".join(lines)

    def find_orb_window(self, transit_planet, natal_long, aspect_angle, exact_dt,
                        orb=3.0, timezone='America/Los_Angeles', max_days=2500):
        """
        Dates either side of a perfection where the aspect is within `orb`.

        Scans coarsely then walks back a day at a time, so a slow planet that
        holds a 3° orb for years is still cheap to bracket.

        Returns:
            Tuple of (entry_date, exit_date) as YYYY-MM-DD strings, either of
            which may be None if the boundary is beyond max_days.
        """
        def orb_on(day_offset):
            jd = self.em.get_julian_day_from_datetime(exact_dt + timedelta(days=day_offset), timezone)
            position = self.em.get_planet_position(transit_planet, jd)
            return self.calculate_aspect_orb(position['longitude'], natal_long, aspect_angle)

        def days_until_out_of_orb(sign):
            coarse = 5
            offset = 0
            while offset < max_days:
                offset += coarse
                if orb_on(sign * offset) > orb:
                    # Back up to the last day still inside the orb
                    for step_back in range(1, coarse + 1):
                        if orb_on(sign * (offset - step_back)) <= orb:
                            return offset - step_back
                    return offset
            return None

        days_before = days_until_out_of_orb(-1)
        days_after = days_until_out_of_orb(1)

        entry_date = ((exact_dt - timedelta(days=days_before)).strftime('%Y-%m-%d')
                      if days_before is not None else None)
        exit_date = ((exact_dt + timedelta(days=days_after)).strftime('%Y-%m-%d')
                     if days_after is not None else None)

        return entry_date, exit_date

    def scan_future_transits(self, chart_key, start_date, end_date,
                            transit_planets=None, aspect_types=None,
                            min_significance='LOW'):
        """
        Scan forward to find upcoming exact aspects (optimized version)

        Args:
            chart_key: Chart identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            transit_planets: List of planets to track (None = all)
            aspect_types: List of aspect types (None = all)
            min_significance: Minimum significance level

        Returns:
            List of upcoming exact aspects
        """
        if transit_planets is None:
            transit_planets = list(PLANETS.keys())

        if aspect_types is None:
            aspect_types = list(ASPECTS.keys())

        significance_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        min_sig_index = significance_order.index(min_significance)

        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days_to_scan = (end - start).days

        upcoming = []
        natal_chart = self.ncm.get_chart(chart_key)
        natal_points = list(PLANETS.keys()) + ['Ascendant', 'MC', 'Descendant', 'IC']

        fast_planets = ['Moon', 'Sun', 'Mercury', 'Venus', 'Mars']

        # For each transit planet and natal point combination
        for transit_planet in transit_planets:
            # Sample finely enough that a fast planet cannot skip an aspect point
            step_hours = 3 if transit_planet == 'Moon' else (12 if transit_planet in fast_planets else 24)

            for natal_point in natal_points:
                if natal_point not in natal_chart['positions']:
                    continue

                natal_long = natal_chart['positions'][natal_point]['longitude']

                for aspect_name in aspect_types:
                    aspect_angle = ASPECTS[aspect_name]['angle']

                    # Check significance first to skip low-priority combos
                    significance, is_challenging = self.rate_aspect_significance(
                        transit_planet, natal_point, aspect_name
                    )
                    sig_index = significance_order.index(significance)
                    if sig_index > min_sig_index:
                        continue  # Skip this combination

                    # Every real perfection in the range. A planet that stations
                    # short of the aspect never goes exact, so it produces no
                    # entry here - and a retrograde that crosses the same point
                    # three times produces three, as it should.
                    crossings = self.find_exact_crossings(
                        transit_planet, natal_long, aspect_angle,
                        start, end, step_hours=step_hours
                    )

                    for hit in crossings:
                        entry_date, exit_date = self.find_orb_window(
                            transit_planet, natal_long, aspect_angle, hit['datetime'], orb=3.0
                        )

                        # Direction changes while the transit is in orb, so the
                        # date range is not read as one steady direction
                        stations = self.find_stations(
                            transit_planet,
                            datetime.strptime(entry_date, '%Y-%m-%d') if entry_date else start,
                            datetime.strptime(exit_date, '%Y-%m-%d') if exit_date else end,
                            natal_long=natal_long, aspect_angle=aspect_angle
                        )

                        upcoming.append({
                            'chart': chart_key,
                            'transit_planet': transit_planet,
                            'natal_point': natal_point,
                            'aspect': aspect_name,
                            'exact_date': hit['datetime'].strftime('%Y-%m-%d'),
                            'exact_datetime': hit['datetime'].strftime('%Y-%m-%d %H:%M'),
                            'exact_retrograde': hit['retrograde'],
                            'entry_date': entry_date,
                            'exit_date': exit_date,
                            'exact_orb': hit['orb'],
                            'stations': [
                                {
                                    'date': station['datetime'].strftime('%Y-%m-%d'),
                                    'type': station['type'],
                                    'orb': station['orb']
                                }
                                for station in stations
                            ],
                            'significance': significance,
                            'is_challenging': is_challenging
                        })

        # Sort by date
        upcoming.sort(key=lambda x: x['exact_date'])

        return upcoming

    def generate_transit_journal(self, chart_key, start_date, days=7, timezone='America/Los_Angeles'):
        """
        Generate a comprehensive transit journal for a given date range

        Args:
            chart_key: Chart identifier
            start_date: Start date in YYYY-MM-DD format
            days: Number of days to include (default 7, max 30)
            timezone: Timezone string

        Returns:
            Dictionary with journal data and plain text output
        """
        days = min(days, 30)  # Cap at 30 days
        start = datetime.strptime(start_date, '%Y-%m-%d')

        # Get chart info
        chart = self.ncm.get_chart(chart_key)
        chart_name = chart['name']

        # Get current planetary positions (at start date noon)
        transit_positions = self.get_transiting_positions(start_date, '12:00', timezone)

        # Build planetary positions section
        planet_positions = {}
        for planet_name in PLANETS.keys():
            pos = transit_positions[planet_name]
            longitude = pos['longitude']
            sign = self.get_sign_from_longitude(longitude)
            degree = int(longitude % 30)
            house = self.ncm.get_house_for_longitude(chart_key, longitude)
            # Direction, so a position never reads as direct when it is not
            if planet_name in OSCILLATING_POINTS:
                retrograde = self.is_prevailing_retrograde(planet_name, start, timezone)
            else:
                retrograde = pos['speed'] < 0

            planet_positions[planet_name] = {
                'longitude': longitude,
                'sign': sign,
                'degree': degree,
                'house': house,
                'retrograde': retrograde,
                'marker': '(Rx)' if retrograde else ''
            }

        # Direction changes inside the journal range. These are the days a
        # planet turns, which is when applying flips to separating without any
        # aspect going exact.
        range_end = start + timedelta(days=days)
        stations_by_date = {}
        for planet_name in PLANETS.keys():
            for station in self.find_stations(planet_name, start, range_end, timezone=timezone):
                stations_by_date.setdefault(station['datetime'].strftime('%Y-%m-%d'), []).append({
                    'planet': planet_name,
                    'type': station['type'],
                    'time': station['datetime'].strftime('%H:%M')
                })

        # Collect all unique transits across the date range
        # We'll track: transit_planet, natal_point, aspect_name -> timeline info
        all_transits = {}
        natal_points_activated = set()

        for day_offset in range(days):
            check_date = start + timedelta(days=day_offset)
            date_str = check_date.strftime('%Y-%m-%d')

            # Get aspects for this day (excluding Moon for now - handle separately)
            aspects = self.find_aspects(chart_key, date_str, max_orb=3, time_str='12:00', timezone=timezone)

            for aspect in aspects:
                if aspect['transit_planet'] == 'Moon':
                    continue  # Handle Moon separately

                key = (aspect['transit_planet'], aspect['natal_point'], aspect['aspect'])
                natal_points_activated.add(aspect['natal_point'])

                if key not in all_transits:
                    # Only the orb window is needed here, not a full timeline
                    summary = self.summarize_transit_window(
                        chart_key,
                        aspect['transit_planet'],
                        aspect['natal_point'],
                        aspect['aspect'],
                        date_str,
                        timezone=timezone
                    )

                    significance, is_challenging = self.rate_aspect_significance(
                        aspect['transit_planet'],
                        aspect['natal_point'],
                        aspect['aspect']
                    )

                    all_transits[key] = {
                        'transit_planet': aspect['transit_planet'],
                        'natal_point': aspect['natal_point'],
                        'aspect': aspect['aspect'],
                        'aspect_word': self.get_aspect_word(aspect['aspect']),
                        'enter_3deg': summary['enter'],
                        # Exact is the 0°00' crossing - a planet that stations
                        # short of the aspect perfects none in this window
                        'exact_date': summary['passes'][0]['date'] if summary['passes'] else None,
                        'passes': summary['passes'],
                        'stations': summary['stations'],
                        'leave_3deg': summary['leave'],
                        'next_exact_after_window': summary['next_exact_after_window'],
                        'significance': significance,
                        'is_challenging': is_challenging
                    }

        # Build natal points being activated with their positions
        natal_activated_info = {}
        for natal_point in natal_points_activated:
            if natal_point in chart['positions']:
                longitude = chart['positions'][natal_point]['longitude']
                sign = self.get_sign_from_longitude(longitude)
                degree = int(longitude % 30)
                house = self.ncm.get_house_for_longitude(chart_key, longitude)
                natal_activated_info[natal_point] = {
                    'longitude': longitude,
                    'sign': sign,
                    'degree': degree,
                    'house': house
                }

        # Generate daily journal entries
        daily_entries = []

        for day_offset in range(days):
            check_date = start + timedelta(days=day_offset)
            date_str = check_date.strftime('%Y-%m-%d')
            day_name = check_date.strftime('%A').upper()
            date_display = check_date.strftime('%B %d').upper()

            entry = {
                'date': date_str,
                'day_name': day_name,
                'date_display': date_display,
                'moon': self._get_moon_daily_info(chart_key, date_str, timezone),
                'stations': stations_by_date.get(date_str, []),
                'events': [],  # Transits entering, going exact, or leaving
                'active_transits': []  # Ongoing transits with current orb
            }

            # Get all aspects for this day
            aspects = self.find_aspects(chart_key, date_str, max_orb=3, time_str='12:00', timezone=timezone)

            for aspect in aspects:
                if aspect['transit_planet'] == 'Moon':
                    continue

                key = (aspect['transit_planet'], aspect['natal_point'], aspect['aspect'])
                transit_info = all_transits.get(key)

                if not transit_info:
                    continue

                # Check for events on this day
                is_event = False
                event_type = None

                exact_today = next(
                    (p for p in transit_info['passes'] if p['date'] == date_str), None
                )

                if transit_info['enter_3deg'] and transit_info['enter_3deg'][:10] == date_str:
                    is_event = True
                    event_type = 'enters orb'
                elif exact_today:
                    is_event = True
                    event_type = 'EXACT'
                elif transit_info['leave_3deg'] and transit_info['leave_3deg'][:10] == date_str:
                    is_event = True
                    event_type = 'exits orb'

                # Format orb
                orb_deg = int(aspect['orb'])
                orb_min = int((aspect['orb'] % 1) * 60)
                orb_str = f"{orb_deg}°{orb_min:02d}'"

                direction = 'approaching' if aspect['is_applying'] else 'separating'

                transit_entry = {
                    'transit_planet': aspect['transit_planet'],
                    'natal_point': aspect['natal_point'],
                    'aspect_word': self.get_aspect_word(aspect['aspect']),
                    'orb': orb_str,
                    'orb_value': aspect['orb'],
                    'direction': direction,
                    'marker': aspect.get('motion_marker', ''),
                    'significance': transit_info['significance'],
                    'is_challenging': transit_info['is_challenging'],
                    'exact_date': transit_info['exact_date'],
                    'exact_retrograde': exact_today['retrograde'] if exact_today else None
                }

                if is_event:
                    transit_entry['event_type'] = event_type
                    entry['events'].append(transit_entry)
                else:
                    entry['active_transits'].append(transit_entry)

            # Sort events and active transits
            entry['events'].sort(key=lambda x: x['orb_value'])
            entry['active_transits'].sort(key=lambda x: x['orb_value'])

            daily_entries.append(entry)

        # Generate plain text output
        plain_text = self._generate_journal_plain_text(
            chart_name, start_date, days, planet_positions,
            natal_activated_info, all_transits, daily_entries
        )

        return {
            'chart_key': chart_key,
            'chart_name': chart_name,
            'start_date': start_date,
            'end_date': (start + timedelta(days=days-1)).strftime('%Y-%m-%d'),
            'days': days,
            'planet_positions': planet_positions,
            'natal_activated': natal_activated_info,
            'transit_overview': list(all_transits.values()),
            'daily_entries': daily_entries,
            'plain_text': plain_text
        }

    def _get_moon_daily_info(self, chart_key, date_str, timezone='America/Los_Angeles'):
        """
        Moon information for one day: sign, house, ingress and every aspect it
        perfects, timed to the minute.

        Times come from real 0°00' crossings rather than from the tightest orb
        of a coarse scan, so they land on the minute the aspect perfects.
        """
        chart = self.ncm.get_chart(chart_key)

        day_start = datetime.strptime(date_str, '%Y-%m-%d')
        day_end = day_start + timedelta(days=1)

        start_long = self.get_longitude_at('Moon', day_start, timezone)
        end_long = self.get_longitude_at('Moon', day_end - timedelta(minutes=1), timezone)

        moon_start_sign = self.get_sign_from_longitude(start_long)
        moon_end_sign = self.get_sign_from_longitude(end_long)
        moon_house = self.ncm.get_house_for_longitude(chart_key, start_long)

        moon_aspects = []

        # Sign change, bisected to the minute
        sign_change = None
        if moon_start_sign != moon_end_sign:
            boundary = math.ceil(start_long / 30) * 30 % 360
            ingress = self.find_exact_crossings(
                'Moon', boundary, 0, day_start, day_end, step_hours=2, timezone=timezone
            )
            if ingress:
                ingress_dt = ingress[0]['datetime']
                sign_change = {
                    'time': ingress_dt.strftime('%H:%M'),
                    'new_sign': moon_end_sign
                }
                moon_aspects.append({
                    'time': sign_change['time'],
                    'time_12hr': self.format_time_12hr(sign_change['time']),
                    'natal_point': None,
                    'aspect_word': None,
                    'sign_change': moon_end_sign
                })

        # Every aspect the Moon perfects during the day
        natal_points = list(PLANETS.keys()) + ['Ascendant', 'MC', 'Descendant', 'IC']

        for natal_point in natal_points:
            if natal_point not in chart['positions']:
                continue

            natal_long = chart['positions'][natal_point]['longitude']

            for aspect_name, aspect_data in ASPECTS.items():
                hits = self.find_exact_crossings(
                    'Moon', natal_long, aspect_data['angle'],
                    day_start, day_end, step_hours=2, timezone=timezone
                )

                for hit in hits:
                    moon_aspects.append({
                        'time': hit['datetime'].strftime('%H:%M'),
                        'time_12hr': self.format_time_12hr(hit['datetime'].strftime('%H:%M')),
                        'natal_point': natal_point,
                        'aspect_word': self.get_aspect_word(aspect_name)
                    })

        moon_aspects.sort(key=lambda x: x['time'])

        return {
            'sign': moon_start_sign,
            'end_sign': moon_end_sign if moon_start_sign != moon_end_sign else None,
            'house': moon_house,
            'sign_change': sign_change,
            'aspects': moon_aspects
        }

    def _generate_journal_plain_text(self, chart_name, start_date, days,
                                      planet_positions, natal_activated,
                                      all_transits, daily_entries):
        """Generate plain text version of the transit journal"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = start + timedelta(days=days-1)

        lines = []

        # Header
        lines.append(f"TRANSIT JOURNAL - {chart_name}")
        lines.append(f"{start.strftime('%B %d')} - {end.strftime('%B %d, %Y')}")

        # A long journal can cross the daylight saving change, so say so
        start_zone = self.timezone_label(start.strftime('%Y-%m-%d'))
        end_zone = self.timezone_label(end.strftime('%Y-%m-%d'))
        if start_zone == end_zone:
            lines.append(f"All times Pacific ({start_zone})")
        else:
            lines.append(f"All times Pacific ({start_zone}, then {end_zone} after the clocks change)")

        lines.append("")
        lines.append("=" * 50)
        lines.append("CURRENT PLANETARY POSITIONS")
        lines.append("=" * 50)
        lines.append("")
        lines.append("Transiting Planets:")

        # Order planets
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter',
                        'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron',
                        'North Node', 'South Node']

        for planet in planet_order:
            if planet in planet_positions:
                p = planet_positions[planet]
                # (Rx) means retrograde right now; unmarked means direct
                marker = f" {p['marker']}" if p.get('marker') else ''
                lines.append(f"  {planet:12} - {p['degree']}° {p['sign']}{marker} (House {p['house']})")

        if natal_activated:
            lines.append("")
            lines.append("Your Natal Points Being Activated:")

            for point_name, p in natal_activated.items():
                lines.append(f"  {point_name:12} - {p['degree']}° {p['sign']} (House {p['house']})")

        lines.append("")
        lines.append("=" * 50)
        lines.append("TRANSIT OVERVIEW")
        lines.append("=" * 50)
        lines.append("")

        # Sort transits by exact date
        sorted_transits = sorted(all_transits.values(),
                                  key=lambda x: x['exact_date'] or '9999-99-99')

        for t in sorted_transits:
            aspect_line = f"{t['transit_planet']} {t['aspect_word']} natal {t['natal_point']}"
            lines.append(aspect_line)

            enter = self._format_date_short(t['enter_3deg']) if t['enter_3deg'] else '--'
            leave = self._format_date_short(t['leave_3deg']) if t['leave_3deg'] else '--'

            # Exact is the 0°00' crossing. A planet that stations short of the
            # aspect never gets one, however tight the orb came.
            if t.get('passes'):
                exact = ', '.join(
                    self._format_date_short(p['date']) + (' (Rx)' if p['retrograde'] else '')
                    for p in t['passes']
                )
            else:
                exact = 'none in this orb window'

            lines.append(f"  Enters orb: {enter}  |  Exact: {exact}  |  Leaves orb: {leave}")

            # The station is why an aspect can come close and turn back
            if t.get('stations'):
                turns = ', '.join(
                    ('goes Rx ' if station['type'] == 'SR' else 'stations direct ')
                    + self._format_date_short(station['date'])
                    + (f" at {self.format_orb(station['orb'])}" if station.get('orb') is not None else '')
                    for station in t['stations']
                )
                # Where the aspect finally perfects, once the planet comes back
                later = t.get('next_exact_after_window')
                if later and not t.get('passes'):
                    later_dt = datetime.strptime(later['date'], '%Y-%m-%d')
                    turns += (f" | next exact {later_dt.strftime('%b %d, %Y')}"
                              + (' (Rx)' if later['retrograde'] else ''))

                lines.append(f"  {t['transit_planet']} {turns}")

            lines.append("")

        lines.append("=" * 50)
        lines.append("DAILY JOURNAL")
        lines.append("=" * 50)

        for entry in daily_entries:
            lines.append("")
            lines.append(f"{entry['day_name']}, {entry['date_display']}")

            # Moon info
            moon = entry['moon']
            moon_line = f"  Moon in {moon['sign']} (House {moon['house']})"
            lines.append(moon_line)

            # Moon aspects with times
            if moon['aspects']:
                for asp in moon['aspects']:
                    if asp.get('sign_change'):
                        lines.append(f"    - {asp['time_12hr']:8} enters {asp['sign_change']}")
                    elif asp['natal_point']:
                        lines.append(f"    - {asp['time_12hr']:8} {asp['aspect_word']} natal {asp['natal_point']}")

            lines.append("")

            # Stations: the day a planet turns around
            for station in entry.get('stations', []):
                turn = 'goes retrograde (Rx)' if station['type'] == 'SR' else 'stations direct'
                lines.append(f"  >> {station['planet']} {turn} at "
                             f"{self.format_time_12hr(station['time'])} "
                             f"{self.timezone_label(entry['date'])}")

            # Events (entering, exact, exiting)
            for event in entry['events']:
                event_marker = ">>"
                if event['event_type'] == 'EXACT':
                    retrograde_note = ' (Rx)' if event.get('exact_retrograde') else ''
                    event_text = (f"  {event_marker} {event['transit_planet']} {event['aspect_word']} "
                                  f"natal {event['natal_point']} is EXACT today{retrograde_note}")
                elif event['event_type'] == 'enters orb':
                    event_text = f"  {event_marker} {event['transit_planet']} {event['aspect_word']} natal {event['natal_point']} enters orb"
                else:
                    event_text = f"  {event_marker} {event['transit_planet']} {event['aspect_word']} natal {event['natal_point']} exits orb"
                lines.append(event_text)

            # Active transits
            for transit in entry['active_transits']:
                # Add context about when it goes exact
                direction_text = transit['direction']
                if transit['direction'] == 'approaching' and transit['exact_date']:
                    exact_dt = datetime.strptime(transit['exact_date'][:10], '%Y-%m-%d')
                    entry_dt = datetime.strptime(entry['date'], '%Y-%m-%d')
                    days_until = (exact_dt - entry_dt).days
                    if days_until == 1:
                        direction_text = "exact tomorrow"
                    elif days_until > 0:
                        direction_text = f"approaching"

                marker = f" {transit['marker']}" if transit.get('marker') else ''
                lines.append(f"  - {transit['transit_planet']}{marker} {transit['aspect_word']} "
                             f"natal {transit['natal_point']} at {transit['orb']} - {direction_text}")

        return "\n".join(lines)

    def _format_date_short(self, date_str):
        """Format date as 'Jan 17' style"""
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%b %d')
        except:
            return date_str


if __name__ == '__main__':
    # Test transit calculator
    print("Testing Transit Calculator...")

    tc = TransitCalculator()

    # Test: Get today's transits for Julian
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')

    print(f"\nTransits for Julian on {today}:")
    dashboard = tc.get_daily_dashboard('julian', today)

    print(f"Total aspects: {dashboard['total_aspects']}")
    print("\nTop 5 aspects:")
    for i, aspect in enumerate(dashboard['aspects'][:5]):
        direction = "→" if aspect['is_applying'] else "←"
        print(f"{i+1}. {aspect['transit_planet']} {aspect['aspect_symbol']} {aspect['natal_point']} "
              f"({aspect['orb']:.2f}° {direction}) [{aspect['significance']}]")
