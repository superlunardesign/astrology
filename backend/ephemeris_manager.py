"""
Swiss Ephemeris Manager
Handles all astronomical calculations using pyswisseph
"""
import swisseph as swe
from datetime import datetime, timedelta, timezone
import pytz
from config import EPHEMERIS_PATH, PLANETS
import os

class EphemerisManager:
    """Manages Swiss Ephemeris calculations"""

    # Crossing searches sample the same planet on the same grid of Julian Days
    # over and over, so positions are memoised.
    CACHE_LIMIT = 200000

    def __init__(self):
        """Initialize Swiss Ephemeris"""
        # Create ephemeris directory if it doesn't exist
        os.makedirs(EPHEMERIS_PATH, exist_ok=True)
        swe.set_ephe_path(EPHEMERIS_PATH)
        self._position_cache = {}

    def get_julian_day(self, date_str, time_str, tz_str):
        """
        Convert date/time to Julian Day

        Args:
            date_str: Date in format 'YYYY-MM-DD'
            time_str: Time in format 'HH:MM'
            tz_str: Timezone string (e.g., 'America/New_York')

        Returns:
            Julian Day number (float)
        """
        # Parse date and time
        date_parts = date_str.split('-')
        time_parts = time_str.split(':')

        year = int(date_parts[0])
        month = int(date_parts[1])
        day = int(date_parts[2])
        hour = int(time_parts[0])
        minute = int(time_parts[1])

        # Create timezone-aware datetime
        tz = pytz.timezone(tz_str)
        dt = datetime(year, month, day, hour, minute)
        dt_tz = tz.localize(dt)

        # Convert to UTC
        dt_utc = dt_tz.astimezone(pytz.UTC)

        # Calculate Julian Day
        jd = swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            dt_utc.hour + dt_utc.minute / 60.0
        )

        return jd

    def get_julian_day_from_datetime(self, dt, tz_str='UTC'):
        """
        Convert a datetime to Julian Day (keeps seconds, unlike get_julian_day)

        Args:
            dt: datetime object (naive datetimes are read in tz_str)
            tz_str: Timezone string (e.g., 'America/Los_Angeles')

        Returns:
            Julian Day number (float)
        """
        tz = pytz.timezone(tz_str)

        if dt.tzinfo is None:
            dt_tz = tz.localize(dt)
        else:
            dt_tz = dt.astimezone(tz)

        dt_utc = dt_tz.astimezone(pytz.UTC)

        return swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
        )

    def get_datetime_from_julian_day(self, jd, tz_str='UTC'):
        """
        Convert a Julian Day back to a naive datetime in tz_str

        Args:
            jd: Julian Day number
            tz_str: Timezone string (e.g., 'America/Los_Angeles')

        Returns:
            datetime (naive, expressed in tz_str)
        """
        year, month, day, hour_float = swe.revjul(jd)

        dt_utc = datetime(year, month, day, tzinfo=pytz.UTC) + timedelta(hours=hour_float)

        return dt_utc.astimezone(pytz.timezone(tz_str)).replace(tzinfo=None)

    def get_planet_position(self, planet_name, jd):
        """
        Get position of a planet at a given Julian Day

        Args:
            planet_name: Name of planet (e.g., 'Sun', 'Moon')
            jd: Julian Day number

        Returns:
            Dictionary with longitude, latitude, distance, speed
        """
        if planet_name not in PLANETS:
            raise ValueError(f"Unknown planet: {planet_name}")

        # Round to the millisecond so repeated searches share cache entries
        cache_key = (planet_name, round(jd, 8))
        cached = self._position_cache.get(cache_key)
        if cached is not None:
            return cached

        planet_id = PLANETS[planet_name]

        # Handle South Node as North Node + 180°
        if planet_name == 'South Node':
            planet_id = PLANETS['North Node']
            result = swe.calc_ut(jd, planet_id)
            position = {
                'longitude': (result[0][0] + 180) % 360,
                'latitude': result[0][1],
                'distance': result[0][2],
                'speed': result[0][3]
            }
        else:
            # Calculate planet position
            result = swe.calc_ut(jd, planet_id)
            position = {
                'longitude': result[0][0],
                'latitude': result[0][1],
                'distance': result[0][2],
                'speed': result[0][3]
            }

        if len(self._position_cache) >= self.CACHE_LIMIT:
            self._position_cache.clear()
        self._position_cache[cache_key] = position

        return position

    def get_house_cusps(self, jd, latitude, longitude, house_system='P'):
        """
        Calculate house cusps and angles

        Args:
            jd: Julian Day number
            latitude: Geographic latitude
            longitude: Geographic longitude
            house_system: House system ('P' for Placidus)

        Returns:
            Dictionary with cusps and angles
        """
        cusps, ascmc = swe.houses(jd, latitude, longitude, house_system.encode())

        return {
            'Ascendant': ascmc[0],
            'MC': ascmc[1],
            'Descendant': (ascmc[0] + 180) % 360,
            'IC': (ascmc[1] + 180) % 360,
            'cusps': list(cusps)
        }

    def get_all_positions(self, date_str, time_str, tz_str, latitude, longitude):
        """
        Get positions of all planets and angles for a given date/time/location

        Args:
            date_str: Date in format 'YYYY-MM-DD'
            time_str: Time in format 'HH:MM'
            tz_str: Timezone string
            latitude: Geographic latitude
            longitude: Geographic longitude

        Returns:
            Dictionary with all planetary positions and angles
        """
        jd = self.get_julian_day(date_str, time_str, tz_str)

        positions = {}

        # Get all planet positions
        for planet_name in PLANETS.keys():
            positions[planet_name] = self.get_planet_position(planet_name, jd)

        # Get angles
        angles = self.get_house_cusps(jd, latitude, longitude)
        for angle_name in ['Ascendant', 'MC', 'Descendant', 'IC']:
            positions[angle_name] = {'longitude': angles[angle_name]}

        return positions

    def normalize_angle(self, angle):
        """Normalize angle to 0-360 range"""
        return angle % 360

    def calculate_aspect_angle(self, long1, long2):
        """
        Calculate the shortest angle between two longitudes

        Args:
            long1: First longitude (0-360)
            long2: Second longitude (0-360)

        Returns:
            Angle between them (0-180)
        """
        diff = abs(long1 - long2)
        if diff > 180:
            diff = 360 - diff
        return diff

    def close_ephemeris(self):
        """Close Swiss Ephemeris"""
        swe.close()


if __name__ == '__main__':
    # Test the ephemeris manager
    em = EphemerisManager()

    # Test getting Sun position for today
    from datetime import date
    today = date.today()
    jd = em.get_julian_day(str(today), '12:00', 'UTC')
    sun_pos = em.get_planet_position('Sun', jd)

    print(f"Sun position for {today}:")
    print(f"Longitude: {sun_pos['longitude']:.2f}°")
    print(f"Speed: {sun_pos['speed']:.5f}°/day")

    em.close_ephemeris()
