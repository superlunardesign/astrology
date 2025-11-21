"""
Natal Chart Manager
Calculates and manages natal chart positions for Christina, Julian, and Davison
"""
from ephemeris_manager import EphemerisManager
from config import NATAL_CHARTS
import json
import os


class NatalChartManager:
    """Manages natal chart data for all three charts"""

    def __init__(self):
        self.em = EphemerisManager()
        self.charts = {}
        self.cache_file = 'natal_charts_cache.json'

    def calculate_natal_chart(self, chart_key):
        """
        Calculate natal chart positions for a given chart

        Args:
            chart_key: Key from NATAL_CHARTS ('christina', 'julian', 'davison')

        Returns:
            Dictionary with all natal positions
        """
        if chart_key not in NATAL_CHARTS:
            raise ValueError(f"Unknown chart: {chart_key}")

        chart_data = NATAL_CHARTS[chart_key]
        location = chart_data['location']

        positions = self.em.get_all_positions(
            chart_data['date'],
            chart_data['time'],
            location['timezone'],
            location['latitude'],
            location['longitude']
        )

        return {
            'name': chart_data['name'],
            'birth_data': {
                'date': chart_data['date'],
                'time': chart_data['time'],
                'location': location
            },
            'positions': positions
        }

    def calculate_all_charts(self):
        """Calculate all three natal charts"""
        for chart_key in NATAL_CHARTS.keys():
            self.charts[chart_key] = self.calculate_natal_chart(chart_key)

    def save_charts_to_cache(self):
        """Save calculated charts to JSON file"""
        # Convert to serializable format
        cache_data = {}
        for chart_key, chart in self.charts.items():
            cache_data[chart_key] = chart

        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

    def load_charts_from_cache(self):
        """Load charts from cache file if it exists"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                self.charts = json.load(f)
            return True
        return False

    def get_chart(self, chart_key):
        """Get a specific natal chart"""
        if chart_key not in self.charts:
            self.charts[chart_key] = self.calculate_natal_chart(chart_key)
        return self.charts[chart_key]

    def get_natal_position(self, chart_key, planet_name):
        """
        Get natal position of a specific planet/point

        Args:
            chart_key: Chart identifier
            planet_name: Name of planet or angle

        Returns:
            Longitude in degrees (0-360)
        """
        chart = self.get_chart(chart_key)
        if planet_name not in chart['positions']:
            raise ValueError(f"Unknown planet/point: {planet_name}")

        return chart['positions'][planet_name]['longitude']

    def format_position(self, longitude):
        """
        Format longitude as zodiac position (e.g., "15° Aries 32'")

        Args:
            longitude: Longitude in degrees (0-360)

        Returns:
            Formatted string
        """
        signs = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]

        sign_num = int(longitude / 30)
        degree = int(longitude % 30)
        minute = int((longitude % 1) * 60)

        return f"{degree}° {signs[sign_num]} {minute:02d}'"

    def print_chart(self, chart_key):
        """Print natal chart in readable format"""
        chart = self.get_chart(chart_key)

        print(f"\n{'='*60}")
        print(f"NATAL CHART: {chart['name']}")
        print(f"{'='*60}")
        print(f"Birth Date: {chart['birth_data']['date']}")
        print(f"Birth Time: {chart['birth_data']['time']}")
        print(f"Location: {chart['birth_data']['location']['city']}, {chart['birth_data']['location']['state']}")
        print(f"\n{'Planet':<15} {'Position':<20} {'Longitude':<12}")
        print(f"{'-'*60}")

        # Print planets
        for planet_name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                           'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
                           'North Node', 'South Node']:
            if planet_name in chart['positions']:
                long = chart['positions'][planet_name]['longitude']
                formatted = self.format_position(long)
                print(f"{planet_name:<15} {formatted:<20} {long:>10.2f}°")

        # Print angles
        print(f"\n{'Angle':<15} {'Position':<20} {'Longitude':<12}")
        print(f"{'-'*60}")
        for angle_name in ['Ascendant', 'MC', 'Descendant', 'IC']:
            if angle_name in chart['positions']:
                long = chart['positions'][angle_name]['longitude']
                formatted = self.format_position(long)
                print(f"{angle_name:<15} {formatted:<20} {long:>10.2f}°")


if __name__ == '__main__':
    # Test natal chart calculation
    print("Calculating natal charts...")

    ncm = NatalChartManager()

    # Calculate all charts
    ncm.calculate_all_charts()

    # Print all charts
    for chart_key in ['christina', 'julian', 'davison']:
        ncm.print_chart(chart_key)

    # Save to cache
    ncm.save_charts_to_cache()
    print(f"\nCharts saved to {ncm.cache_file}")
