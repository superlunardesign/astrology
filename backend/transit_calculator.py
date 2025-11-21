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
                            'transit_speed': transit_speed
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

    def calculate_aspect_timeline(self, chart_key, transit_planet, natal_point,
                                  aspect_name, reference_date):
        """
        Calculate complete timeline for an aspect (entry, exact, exit dates)

        Args:
            chart_key: Chart identifier
            transit_planet: Name of transiting planet
            natal_point: Name of natal planet/point
            aspect_name: Type of aspect
            reference_date: Reference date (YYYY-MM-DD)

        Returns:
            Dictionary with timeline information
        """
        aspect_angle = ASPECTS[aspect_name]['angle']
        natal_long = self.ncm.get_natal_position(chart_key, natal_point)

        # Find dates when aspect enters and leaves different orbs
        timeline = {
            'enter_5deg': None,
            'enter_3deg': None,
            'enter_1deg': None,
            'exact_date': None,
            'exact_orb': None,
            'leave_1deg': None,
            'leave_3deg': None,
            'leave_5deg': None
        }

        # Search backward and forward from reference date
        ref = datetime.strptime(reference_date, '%Y-%m-%d')

        # Find exact date first (search ±365 days)
        exact_date, exact_orb = self.find_exact_aspect_date(
            chart_key, transit_planet, natal_point, aspect_name,
            (ref - timedelta(days=365)).strftime('%Y-%m-%d'),
            max_days=730
        )

        timeline['exact_date'] = exact_date
        timeline['exact_orb'] = exact_orb

        if exact_date:
            exact = datetime.strptime(exact_date, '%Y-%m-%d')

            # Search backward from exact date for entry points
            for days_back in range(1, 730):
                check_date = exact - timedelta(days=days_back)
                date_str = check_date.strftime('%Y-%m-%d')

                jd = self.em.get_julian_day(date_str, '12:00', 'UTC')
                transit_pos = self.em.get_planet_position(transit_planet, jd)
                transit_long = transit_pos['longitude']

                orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

                if orb <= 1 and not timeline['enter_1deg']:
                    timeline['enter_1deg'] = date_str
                if orb <= 3 and not timeline['enter_3deg']:
                    timeline['enter_3deg'] = date_str
                if orb <= 5 and not timeline['enter_5deg']:
                    timeline['enter_5deg'] = date_str

                if orb > 5:
                    break

            # Search forward from exact date for exit points
            for days_forward in range(1, 730):
                check_date = exact + timedelta(days=days_forward)
                date_str = check_date.strftime('%Y-%m-%d')

                jd = self.em.get_julian_day(date_str, '12:00', 'UTC')
                transit_pos = self.em.get_planet_position(transit_planet, jd)
                transit_long = transit_pos['longitude']

                orb = self.calculate_aspect_orb(transit_long, natal_long, aspect_angle)

                if orb > 1 and not timeline['leave_1deg']:
                    timeline['leave_1deg'] = date_str
                if orb > 3 and not timeline['leave_3deg']:
                    timeline['leave_3deg'] = date_str
                if orb > 5 and not timeline['leave_5deg']:
                    timeline['leave_5deg'] = date_str

                if orb > 5 and timeline['leave_5deg']:
                    break

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
        # Check if it's a critical transit
        for t_planet, n_points in CRITICAL_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                is_challenging = aspect_name in ['Conjunction', 'Square', 'Opposition']
                return ('CRITICAL', is_challenging)

        # Check if it's a high significance transit
        for t_planet, n_points in HIGH_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                is_challenging = aspect_name in ['Square', 'Opposition']
                return ('HIGH', is_challenging)

        # Check if it's a medium significance transit
        for t_planet, n_points in MEDIUM_TRANSITS:
            if transit_planet == t_planet and natal_point in n_points:
                is_challenging = aspect_name in ['Square', 'Opposition']
                return ('MEDIUM', is_challenging)

        # Default to low significance
        is_challenging = aspect_name in ['Square', 'Opposition']
        return ('LOW', is_challenging)

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

        # Calculate exact dates and timelines for each aspect
        for aspect in aspects:
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

        return {
            'chart': chart_key,
            'date': date_str,
            'time': time_str,
            'timezone': timezone,
            'total_aspects': len(aspects),
            'aspects': aspects
        }

    def scan_future_transits(self, chart_key, start_date, end_date,
                            transit_planets=None, aspect_types=None,
                            min_significance='LOW'):
        """
        Scan forward to find upcoming exact aspects

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

        # For each transit planet and natal point combination
        for transit_planet in transit_planets:
            for natal_point in natal_points:
                if natal_point not in natal_chart['positions']:
                    continue

                for aspect_name in aspect_types:
                    # Find exact date
                    exact_date, exact_orb = self.find_exact_aspect_date(
                        chart_key, transit_planet, natal_point, aspect_name,
                        start_date, max_days=days_to_scan
                    )

                    if exact_date and exact_orb < 0.5:  # Only include if very close to exact
                        # Check significance
                        significance, is_challenging = self.rate_aspect_significance(
                            transit_planet, natal_point, aspect_name
                        )

                        sig_index = significance_order.index(significance)
                        if sig_index <= min_sig_index:
                            upcoming.append({
                                'chart': chart_key,
                                'transit_planet': transit_planet,
                                'natal_point': natal_point,
                                'aspect': aspect_name,
                                'exact_date': exact_date,
                                'exact_orb': exact_orb,
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
