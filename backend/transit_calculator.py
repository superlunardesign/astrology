"""
Transit Calculator
Core logic for calculating transits, aspects, and timelines
"""
from datetime import datetime, timedelta
from ephemeris_manager import EphemerisManager
from natal_charts import NatalChartManager
from config import ASPECTS, PLANETS, CRITICAL_TRANSITS, HIGH_TRANSITS, MEDIUM_TRANSITS
import math


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

        aspects = []

        # Check each transiting planet
        for transit_planet in PLANETS.keys():
            transit_long = transit_positions[transit_planet]['longitude']
            transit_speed = transit_positions[transit_planet]['speed']

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
                        # Determine if applying or separating
                        is_applying = self.is_aspect_applying(
                            transit_long, natal_long, aspect_angle, transit_speed
                        )

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
                            'transit_house': transit_house
                        })

        # Sort by orb (closest first)
        aspects.sort(key=lambda x: x['orb'])

        return aspects

    def is_aspect_applying(self, transit_long, natal_long, aspect_angle, transit_speed):
        """
        Determine if an aspect is applying or separating

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

    def find_exact_aspect_date(self, chart_key, transit_planet, natal_point, aspect_name,
                               start_date, max_days=365):
        """
        Find the exact date when an aspect goes exact

        Args:
            chart_key: Chart identifier
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect
            start_date: Date to start searching from (YYYY-MM-DD)
            max_days: Maximum days to search forward

        Returns:
            Date string when aspect goes exact, or None
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        start = datetime.strptime(start_date, '%Y-%m-%d')
        min_orb = float('inf')
        best_date = None

        for days in range(max_days):
            check_date = start + timedelta(days=days)
            date_str = check_date.strftime('%Y-%m-%d')

            jd = self.em.get_julian_day(date_str, '12:00', 'UTC')
            transit_pos = self.em.get_planet_position(transit_planet, jd)
            transit_long = transit_pos['longitude']

            orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

            if orb < min_orb:
                min_orb = orb
                best_date = date_str

            # If orb is increasing and we found a minimum, we passed the exact date
            if orb > min_orb and min_orb < 0.1:
                break

        return best_date, min_orb

    def find_exact_aspect_datetime(self, chart_key, transit_planet, natal_point, aspect_name,
                                    start_date, start_time='12:00', timezone='America/Los_Angeles',
                                    max_hours=168):
        """
        Find the exact date AND time when an aspect goes exact (for fast-moving planets)

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
            Tuple of (datetime_str, orb) - datetime in format 'YYYY-MM-DD HH:MM'
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        # Determine search interval based on planet speed
        # Fast planets: Moon (12°/day), Sun/Mercury/Venus/Mars (~1°/day)
        fast_planets = ['Moon', 'Sun', 'Mercury', 'Venus', 'Mars']
        if transit_planet in fast_planets:
            # Search in 15-minute intervals for fast planets
            interval_minutes = 15
        else:
            # Search in 6-hour intervals for slow planets
            interval_minutes = 360

        start_dt = datetime.strptime(f"{start_date} {start_time}", '%Y-%m-%d %H:%M')
        min_orb = float('inf')
        best_datetime = None

        intervals = (max_hours * 60) // interval_minutes

        for i in range(intervals):
            check_dt = start_dt + timedelta(minutes=i * interval_minutes)
            date_str = check_dt.strftime('%Y-%m-%d')
            time_str = check_dt.strftime('%H:%M')

            jd = self.em.get_julian_day(date_str, time_str, timezone)
            transit_pos = self.em.get_planet_position(transit_planet, jd)
            transit_long = transit_pos['longitude']

            orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

            if orb < min_orb:
                min_orb = orb
                best_datetime = check_dt.strftime('%Y-%m-%d %H:%M')

            # If orb is increasing significantly and we found a minimum, we passed the exact time
            if orb > min_orb + 0.01 and min_orb < 0.1:
                break

        return best_datetime, min_orb

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
            'exact_dates': [],  # Can have multiple exact passes due to retrograde
            'exact_date': None,  # Nearest exact date to reference
            'exact_orb': None,
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

        # Step 4: Find the nearest exact date to reference
        # Search both directions to find the closest exact point
        exact_date, exact_orb = self.find_exact_aspect_date(
            chart_key, transit_planet, natal_point, aspect_name,
            (ref - timedelta(days=60)).strftime('%Y-%m-%d'),
            max_days=120  # ±60 days from reference
        )

        timeline['exact_date'] = exact_date
        timeline['exact_orb'] = exact_orb

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

            # Find precise exact time using binary search
            if timeline['exact_date']:
                exact_dt = datetime.strptime(timeline['exact_date'], '%Y-%m-%d')
                # Binary search for minimum orb within the day
                low = datetime.combine(exact_dt.date(), datetime.min.time())
                high = low + timedelta(hours=24)

                for _ in range(10):  # ~1 minute precision
                    mid = low + (high - low) / 2
                    orb_low = get_orb_for_datetime(low)
                    orb_mid = get_orb_for_datetime(mid)
                    orb_high = get_orb_for_datetime(high)

                    if orb_low < orb_mid:
                        high = mid
                    elif orb_high < orb_mid:
                        low = mid
                    else:
                        # Minimum is around mid, narrow both sides
                        low = low + (mid - low) / 2
                        high = mid + (high - mid) / 2

                best_time = low + (high - low) / 2
                best_orb = get_orb_for_datetime(best_time)
                timeline['exact_datetime'] = best_time.strftime('%Y-%m-%d %H:%M')
                timeline['exact_orb'] = best_orb

        return timeline

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

        # Fast planets that get exact time calculations
        fast_planets = ['Moon', 'Sun', 'Mercury', 'Venus', 'Mars']

        # Calculate exact dates/times for each aspect
        for aspect in aspects:
            # For fast planets, calculate exact time
            if aspect['transit_planet'] in fast_planets and aspect['is_applying']:
                exact_datetime, exact_orb = self.find_exact_aspect_datetime(
                    chart_key,
                    aspect['transit_planet'],
                    aspect['natal_point'],
                    aspect['aspect'],
                    date_str,
                    time_str,
                    timezone,
                    max_hours=168  # Search up to 7 days ahead
                )
                if exact_datetime:
                    aspect['exact_datetime'] = exact_datetime
                    aspect['exact_orb'] = exact_orb
                    # Also set the date portion
                    aspect['exact_date'] = exact_datetime.split(' ')[0]
                else:
                    aspect['exact_datetime'] = None
                    aspect['exact_date'] = None
                    aspect['exact_orb'] = None
            else:
                # For slow planets or separating aspects, use date-only search
                exact_date, exact_orb = self.find_exact_aspect_date(
                    chart_key,
                    aspect['transit_planet'],
                    aspect['natal_point'],
                    aspect['aspect'],
                    date_str,
                    max_days=180
                )
                aspect['exact_date'] = exact_date
                aspect['exact_orb'] = exact_orb
                aspect['exact_datetime'] = None

            # Add sign information for plain text output
            aspect['transit_sign'] = self.get_sign_from_longitude(aspect['transit_longitude'])
            aspect['natal_sign'] = self.get_sign_from_longitude(aspect['natal_longitude'])

        # Generate plain text list
        plain_text_lines = self.generate_plain_text_list(chart_key, date_str, time_str, aspects)

        return {
            'chart': chart_key,
            'date': date_str,
            'time': time_str,
            'timezone': timezone,
            'total_aspects': len(aspects),
            'aspects': aspects,
            'plain_text': plain_text_lines
        }

    def generate_plain_text_list(self, chart_key, date_str, time_str, aspects):
        """Generate a plain text list of aspects for easy copying"""
        chart_name = self.ncm.get_chart(chart_key)['name']
        time_12hr = self.format_time_12hr(time_str)

        # Format the date nicely
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        date_formatted = dt.strftime('%B %d, %Y')

        lines = [f"{date_formatted} Transits at {time_12hr} PST", f"{chart_name}", ""]

        for aspect in aspects:
            direction = "applying" if aspect['is_applying'] else "separating"
            orb_str = f"{int(aspect['orb'])}°{int((aspect['orb'] % 1) * 60):02d}'"

            # Build the aspect description
            transit_planet = aspect['transit_planet']
            transit_sign = aspect['transit_sign']
            aspect_word = self.get_aspect_word(aspect['aspect'])
            natal_point = aspect['natal_point']
            natal_sign = aspect['natal_sign']

            line = f"{transit_planet} in {transit_sign} {aspect_word} {natal_point} in {natal_sign} at {orb_str} {direction}"

            # Add exact time/date info
            if aspect.get('exact_datetime') and aspect['is_applying']:
                exact_dt = datetime.strptime(aspect['exact_datetime'], '%Y-%m-%d %H:%M')
                exact_date_fmt = exact_dt.strftime('%m-%d-%Y')
                exact_time_fmt = self.format_time_12hr(exact_dt.strftime('%H:%M'))
                line += f" | Exact {exact_date_fmt} ~{exact_time_fmt} PST"
            elif aspect.get('exact_date') and aspect['is_applying']:
                exact_dt = datetime.strptime(aspect['exact_date'], '%Y-%m-%d')
                exact_date_fmt = exact_dt.strftime('%m-%d-%Y')
                line += f" | Exact ~{exact_date_fmt}"

            lines.append(line)

        return "\n".join(lines)

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

        # Pre-calculate transit positions for all days at once (OPTIMIZATION)
        # This avoids recalculating the same planet positions repeatedly
        transit_cache = {}
        for day_offset in range(days_to_scan + 1):
            check_date = start + timedelta(days=day_offset)
            date_str = check_date.strftime('%Y-%m-%d')
            jd = self.em.get_julian_day(date_str, '12:00', 'UTC')

            transit_cache[date_str] = {}
            for transit_planet in transit_planets:
                transit_cache[date_str][transit_planet] = self.em.get_planet_position(transit_planet, jd)

        upcoming = []
        natal_chart = self.ncm.get_chart(chart_key)
        natal_points = list(PLANETS.keys()) + ['Ascendant', 'MC', 'Descendant', 'IC']

        # For each transit planet and natal point combination
        for transit_planet in transit_planets:
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

                    # Find minimum orb in our cached data
                    min_orb = float('inf')
                    best_date = None
                    prev_orb = None

                    for day_offset in range(days_to_scan + 1):
                        check_date = start + timedelta(days=day_offset)
                        date_str = check_date.strftime('%Y-%m-%d')

                        transit_long = transit_cache[date_str][transit_planet]['longitude']
                        orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

                        if orb < min_orb:
                            min_orb = orb
                            best_date = date_str

                        # Optimization: if orb was decreasing and now increasing,
                        # and we found a good aspect, we can stop
                        if prev_orb is not None and orb > prev_orb and min_orb < 1.0:
                            # Check if we should continue (planet might come back due to retrograde)
                            if orb > 5:  # Far enough away, probably won't come back
                                break

                        prev_orb = orb

                    if best_date and min_orb < 0.5:  # Only include if very close to exact
                        exact_dt = datetime.strptime(best_date, '%Y-%m-%d')

                        # Find when aspect enters 3° orb before exact date
                        entry_date = None
                        for entry_offset in range(1, 365):  # Search backward up to a year
                            entry_check = exact_dt - timedelta(days=entry_offset)
                            entry_date_str = entry_check.strftime('%Y-%m-%d')

                            # Check if we have cached data, otherwise calculate
                            if entry_date_str in transit_cache:
                                entry_long = transit_cache[entry_date_str][transit_planet]['longitude']
                            else:
                                jd = self.em.get_julian_day(entry_date_str, '12:00', 'UTC')
                                entry_pos = self.em.get_planet_position(transit_planet, jd)
                                entry_long = entry_pos['longitude']

                            entry_orb = self.calculate_aspect_orb(entry_long, natal_long, aspect_angle)

                            if entry_orb > 3.0:
                                # We went too far back, the entry is the previous day
                                entry_date = (entry_check + timedelta(days=1)).strftime('%Y-%m-%d')
                                break

                        # Find when aspect exits 3° orb after exact date
                        exit_date = None
                        for exit_offset in range(1, 365):  # Search up to a year
                            exit_check = exact_dt + timedelta(days=exit_offset)
                            exit_date_str = exit_check.strftime('%Y-%m-%d')

                            # Check if we have cached data, otherwise calculate
                            if exit_date_str in transit_cache:
                                exit_long = transit_cache[exit_date_str][transit_planet]['longitude']
                            else:
                                jd = self.em.get_julian_day(exit_date_str, '12:00', 'UTC')
                                exit_pos = self.em.get_planet_position(transit_planet, jd)
                                exit_long = exit_pos['longitude']

                            exit_orb = self.calculate_aspect_orb(exit_long, natal_long, aspect_angle)

                            if exit_orb > 3.0:
                                exit_date = exit_date_str
                                break

                        upcoming.append({
                            'chart': chart_key,
                            'transit_planet': transit_planet,
                            'natal_point': natal_point,
                            'aspect': aspect_name,
                            'exact_date': best_date,
                            'entry_date': entry_date,
                            'exit_date': exit_date,
                            'exact_orb': min_orb,
                            'significance': significance,
                            'is_challenging': is_challenging
                        })

        # Sort by date
        upcoming.sort(key=lambda x: x['exact_date'])

        return upcoming


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
