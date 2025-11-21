"""
Natal Chart Manager
Uses pre-calculated positions from Time Nomad for accuracy
"""
from config import NATAL_POSITIONS


class NatalChartManager:
    """Manages natal chart data for all three charts using pre-calculated positions"""

    def __init__(self):
        self.charts = {}
        self._load_precalculated_positions()

    def _load_precalculated_positions(self):
        """Load pre-calculated natal positions from config"""
        for chart_key, chart_data in NATAL_POSITIONS.items():
            self.charts[chart_key] = {
                'name': chart_data['name'],
                'birth_data': chart_data['birth_data'],
                'positions': {}
            }

            # Convert simple longitude values to position dict format
            for point_name, longitude in chart_data['positions'].items():
                self.charts[chart_key]['positions'][point_name] = {
                    'longitude': longitude
                }

    def get_chart(self, chart_key):
        """Get a specific natal chart"""
        if chart_key not in self.charts:
            raise ValueError(f"Unknown chart: {chart_key}")
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
        print(f"Birth: {chart['birth_data']['date']} at {chart['birth_data']['time']}")
        print(f"Location: {chart['birth_data']['location']}")
        print(f"\n{'Planet':<15} {'Position':<20} {'Longitude':<12}")
        print(f"{'-'*60}")

        # Print planets
        for planet_name in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                           'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
                           'North Node', 'South Node', 'Chiron']:
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

    def calculate_all_charts(self):
        """For compatibility - positions are already loaded"""
        pass

    def save_charts_to_cache(self):
        """For compatibility - not needed with pre-calculated positions"""
        pass

    def load_charts_from_cache(self):
        """For compatibility - always returns True since positions are pre-loaded"""
        return True


if __name__ == '__main__':
    # Test natal chart display
    print("Loading pre-calculated natal charts from Time Nomad...")

    ncm = NatalChartManager()

    # Print all charts
    for chart_key in ['christina', 'julian', 'davison']:
        ncm.print_chart(chart_key)

    # Verify specific positions
    print("\n" + "="*60)
    print("VERIFICATION OF KEY POSITIONS:")
    print("="*60)

    julian = ncm.get_chart('julian')
    print(f"\nJulian's North Node: {ncm.format_position(julian['positions']['North Node']['longitude'])} ({julian['positions']['North Node']['longitude']:.2f}°)")
    print(f"Julian's Mercury: {ncm.format_position(julian['positions']['Mercury']['longitude'])} ({julian['positions']['Mercury']['longitude']:.2f}°)")
    print(f"Julian's Ascendant: {ncm.format_position(julian['positions']['Ascendant']['longitude'])} ({julian['positions']['Ascendant']['longitude']:.2f}°)")
