"""
Configuration for the Transit Tracker application
Uses exact natal positions from Time Nomad for accuracy
"""
import os

# Ephemeris path
EPHEMERIS_PATH = os.path.join(os.path.dirname(__file__), '..', 'ephemeris')

# Helper function to convert zodiac position to longitude
def zodiac_to_longitude(degrees, minutes, seconds, sign):
    """Convert zodiac position to ecliptic longitude (0-360)

    Args:
        degrees: Degrees within the sign (0-29)
        minutes: Arc minutes (0-59)
        seconds: Arc seconds (0-59.99)
        sign: Zodiac sign name

    Returns:
        Ecliptic longitude in degrees (0-360)
    """
    signs = {
        'Aries': 0, 'Taurus': 30, 'Gemini': 60, 'Cancer': 90,
        'Leo': 120, 'Virgo': 150, 'Libra': 180, 'Scorpio': 210,
        'Sagittarius': 240, 'Capricorn': 270, 'Aquarius': 300, 'Pisces': 330
    }
    return signs[sign] + degrees + (minutes / 60) + (seconds / 3600)


# Pre-calculated natal positions from Time Nomad
# This ensures exact match with user's astrology software
NATAL_POSITIONS = {
    'christina': {
        'name': 'Christina',
        'birth_data': {
            'date': '1992-03-26',
            'time': '09:04',
            'location': 'Indianapolis, Indiana'
        },
        'positions': {
            # Exact positions from Time Nomad with arc seconds
            'Sun': zodiac_to_longitude(6, 9, 40.66, 'Aries'),           # 6°09′40.66″ Aries
            'Moon': zodiac_to_longitude(11, 26, 6.26, 'Capricorn'),     # 11°26′6.26″ Capricorn
            'Mercury': zodiac_to_longitude(6, 13, 37.60, 'Aries'),      # 6°13′37.60″ Aries
            'Venus': zodiac_to_longitude(15, 32, 0, 'Pisces'),          # 15°32′ Pisces
            'Mars': zodiac_to_longitude(28, 50, 0, 'Aquarius'),         # 28°50′ Aquarius
            'Jupiter': zodiac_to_longitude(6, 29, 0, 'Virgo'),          # 6°29′ Virgo
            'Saturn': zodiac_to_longitude(15, 27, 0, 'Aquarius'),       # 15°27′ Aquarius
            'Uranus': zodiac_to_longitude(17, 43, 0, 'Capricorn'),      # 17°43′ Capricorn
            'Neptune': zodiac_to_longitude(18, 47, 0, 'Capricorn'),     # 18°47′ Capricorn
            'Pluto': zodiac_to_longitude(22, 41, 0, 'Scorpio'),         # 22°41′ Scorpio
            'North Node': zodiac_to_longitude(5, 16, 22.97, 'Capricorn'),   # 5°16′22.97″ Capricorn (TrueNode)
            'South Node': zodiac_to_longitude(5, 16, 22.97, 'Cancer'),      # Opposite of North Node
            'Chiron': zodiac_to_longitude(3, 21, 0, 'Cancer'),          # 3°21′ Cancer
            'Ascendant': zodiac_to_longitude(28, 53, 0, 'Taurus'),      # 28°53′ Taurus
            'MC': zodiac_to_longitude(6, 43, 0, 'Aquarius'),            # 6°43′ Aquarius
            'Descendant': zodiac_to_longitude(28, 53, 0, 'Scorpio'),    # Opposite of Ascendant
            'IC': zodiac_to_longitude(6, 43, 0, 'Leo'),                 # Opposite of MC
        }
    },
    'julian': {
        'name': 'Julian',
        'birth_data': {
            'date': '2002-02-16',
            'time': '00:30',
            'location': 'Olympia, Washington'
        },
        'positions': {
            # Exact positions from Time Nomad with arc seconds
            'Sun': zodiac_to_longitude(27, 29, 19, 'Aquarius'),        # 27°29′19″ Aquarius
            'Moon': zodiac_to_longitude(11, 23, 49, 'Aries'),          # 11°23′49″ Aries
            'Mercury': zodiac_to_longitude(1, 37, 47, 'Aquarius'),     # 1°37′47″ Aquarius
            'Venus': zodiac_to_longitude(5, 23, 0, 'Pisces'),          # 5°23′ Pisces
            'Mars': zodiac_to_longitude(20, 32, 0, 'Aries'),           # 20°32′ Aries
            'Jupiter': zodiac_to_longitude(5, 55, 0, 'Cancer'),        # 5°55′ Cancer
            'Saturn': zodiac_to_longitude(8, 6, 0, 'Gemini'),          # 8°06′ Gemini
            'Uranus': zodiac_to_longitude(24, 58, 0, 'Aquarius'),      # 24°58′ Aquarius
            'Neptune': zodiac_to_longitude(9, 10, 0, 'Aquarius'),      # 9°10′ Aquarius
            'Pluto': zodiac_to_longitude(17, 20, 0, 'Sagittarius'),    # 17°20′ Sagittarius
            'North Node': zodiac_to_longitude(20, 50, 57.83, 'Gemini'),    # 20°50′57.83″ Gemini (TrueNode)
            'South Node': zodiac_to_longitude(20, 50, 57.83, 'Sagittarius'), # Opposite of North Node
            'Chiron': zodiac_to_longitude(6, 38, 0, 'Capricorn'),      # 6°38′ Capricorn
            'Ascendant': zodiac_to_longitude(14, 55, 0, 'Scorpio'),    # 14°55′ Scorpio
            'MC': zodiac_to_longitude(28, 37, 0, 'Leo'),               # 28°37′ Leo
            'Descendant': zodiac_to_longitude(14, 55, 0, 'Taurus'),    # Opposite of Ascendant
            'IC': zodiac_to_longitude(28, 37, 0, 'Aquarius'),          # Opposite of MC
        }
    },
    'davison': {
        'name': 'Davison',
        'birth_data': {
            'date': '1997-03-07',
            'time': '03:58',
            'location': 'Lusk, Wyoming'
        },
        'positions': {
            # Exact positions from Time Nomad with arc seconds
            'Sun': zodiac_to_longitude(16, 54, 54, 'Pisces'),          # 16°54′54″ Pisces
            'Moon': zodiac_to_longitude(24, 20, 0, 'Aquarius'),        # 24°20′0″ Aquarius
            'Mercury': zodiac_to_longitude(13, 8, 10, 'Pisces'),       # 13°08′10″ Pisces
            'Venus': zodiac_to_longitude(10, 21, 0, 'Pisces'),         # 10°21′ Pisces
            'Mars': zodiac_to_longitude(0, 29, 6, 'Libra'),            # 0°29′6″ Libra
            'Jupiter': zodiac_to_longitude(10, 11, 0, 'Aquarius'),     # 10°11′ Aquarius
            'Saturn': zodiac_to_longitude(7, 20, 0, 'Aries'),          # 7°20′ Aries
            'Uranus': zodiac_to_longitude(6, 56, 0, 'Aquarius'),       # 6°56′ Aquarius
            'Neptune': zodiac_to_longitude(29, 8, 0, 'Capricorn'),     # 29°08′ Capricorn
            'Pluto': zodiac_to_longitude(5, 36, 0, 'Sagittarius'),     # 5°36′ Sagittarius
            'North Node': zodiac_to_longitude(28, 37, 57.19, 'Virgo'),    # 28°37′57.19″ Virgo (TrueNode)
            'South Node': zodiac_to_longitude(28, 37, 57.19, 'Pisces'),   # Opposite of North Node
            'Chiron': zodiac_to_longitude(1, 39, 0, 'Cancer'),         # 1°39′ Cancer
            'Ascendant': zodiac_to_longitude(21, 57, 0, 'Capricorn'),  # 21°57′ Capricorn
            'MC': zodiac_to_longitude(17, 43, 0, 'Scorpio'),           # 17°43′ Scorpio
            'Descendant': zodiac_to_longitude(21, 57, 0, 'Cancer'),    # Opposite of Ascendant
            'IC': zodiac_to_longitude(17, 43, 0, 'Taurus'),            # Opposite of MC
        }
    },
    'anna': {
        'name': 'Anna',
        'birth_data': {
            'date': '1992-04-27',
            'time': '21:15',
            'location': 'Seattle, Washington'
        },
        'positions': {
            # Exact positions from Time Nomad with arc seconds
            'Sun': zodiac_to_longitude(8, 7, 29.77, 'Taurus'),         # 8°07′29.77″ Taurus
            'Moon': zodiac_to_longitude(14, 2, 49.01, 'Pisces'),       # 14°02′49.01″ Pisces
            'Mercury': zodiac_to_longitude(11, 27, 58.04, 'Aries'),    # 11°27′58.04″ Aries
            'Venus': zodiac_to_longitude(25, 42, 56.93, 'Aries'),      # 25°42′56.93″ Aries
            'Mars': zodiac_to_longitude(24, 3, 20.47, 'Pisces'),       # 24°03′20.47″ Pisces
            'Jupiter': zodiac_to_longitude(4, 38, 17.31, 'Virgo'),     # 4°38′17.31″ Virgo
            'Saturn': zodiac_to_longitude(17, 44, 15.75, 'Aquarius'),  # 17°44′15.75″ Aquarius
            'Uranus': zodiac_to_longitude(17, 59, 42.99, 'Capricorn'), # 17°59′42.99″ Capricorn
            'Neptune': zodiac_to_longitude(18, 56, 13.23, 'Capricorn'),# 18°56′13.23″ Capricorn
            'Pluto': zodiac_to_longitude(21, 57, 1.20, 'Scorpio'),     # 21°57′1.20″ Scorpio
            'North Node': zodiac_to_longitude(2, 18, 10.00, 'Capricorn'),  # 2°18′10.00″ Capricorn (TrueNode)
            'South Node': zodiac_to_longitude(2, 18, 10.00, 'Cancer'),     # Opposite of North Node
            'Ascendant': zodiac_to_longitude(19, 48, 35.68, 'Scorpio'),    # 19°48′35.68″ Scorpio
            'MC': zodiac_to_longitude(6, 1, 53.69, 'Virgo'),           # 6°01′53.69″ Virgo
            'Descendant': zodiac_to_longitude(19, 48, 35.68, 'Taurus'),    # Opposite of Ascendant
            'IC': zodiac_to_longitude(6, 1, 53.69, 'Pisces'),          # Opposite of MC
        }
    },
    'superlunar': {
        'name': 'Superlunar Design Co.',
        'birth_data': {
            'date': '2022-03-01',
            'time': '17:07',
            'location': 'Monterey, California'
        },
        'positions': {
            # Positions from Time Nomad
            'Sun': zodiac_to_longitude(11, 25, 19, 'Pisces'),          # 11°25′19″ Pisces
            'Moon': zodiac_to_longitude(2, 29, 21, 'Pisces'),          # 2°29′21″ Pisces
            'Mercury': zodiac_to_longitude(18, 5, 5, 'Aquarius'),      # 18°05′05″ Aquarius
            'Venus': zodiac_to_longitude(26, 26, 6, 'Capricorn'),      # 26°26′06″ Capricorn
            'Mars': zodiac_to_longitude(26, 51, 13, 'Capricorn'),      # 26°51′13″ Capricorn
            'Jupiter': zodiac_to_longitude(14, 7, 2, 'Pisces'),        # 14°07′02″ Pisces
            'Saturn': zodiac_to_longitude(18, 55, 6, 'Aquarius'),      # 18°55′06″ Aquarius
            'Uranus': zodiac_to_longitude(11, 34, 56, 'Taurus'),       # 11°34′56″ Taurus
            'Neptune': zodiac_to_longitude(22, 26, 27, 'Pisces'),      # 22°26′27″ Pisces
            'Pluto': zodiac_to_longitude(27, 48, 0, 'Capricorn'),      # 27°48′00″ Capricorn
            'North Node': zodiac_to_longitude(25, 32, 41, 'Taurus'),   # 25°32′41″ Taurus
            'South Node': zodiac_to_longitude(25, 32, 41, 'Scorpio'),  # 25°32′41″ Scorpio
            'Chiron': zodiac_to_longitude(0, 0, 0, 'Aries'),           # Placeholder - Chiron not provided
            'Ascendant': zodiac_to_longitude(1, 0, 31, 'Virgo'),       # 1°00′31″ Virgo
            'MC': zodiac_to_longitude(26, 57, 15, 'Taurus'),           # 26°57′15″ Taurus
            'Descendant': zodiac_to_longitude(1, 0, 31, 'Pisces'),     # 1°00′31″ Pisces
            'IC': zodiac_to_longitude(26, 57, 15, 'Scorpio'),          # 26°57′15″ Scorpio
        }
    },
    'jarrett': {
        'name': 'Jarrett',
        'birth_data': {
            'date': '1998-03-23',
            'time': '17:54',
            'location': 'Indianapolis, Indiana'
        },
        'positions': {
            # Positions from Time Nomad
            'Sun': zodiac_to_longitude(3, 6, 13.07, 'Aries'),          # 3°06′13.07″ Aries
            'Moon': zodiac_to_longitude(5, 41, 31.61, 'Aquarius'),     # 5°41′31.61″ Aquarius
            'Mercury': zodiac_to_longitude(20, 32, 14.09, 'Aries'),    # 20°32′14.09″ Aries
            'Venus': zodiac_to_longitude(16, 41, 7.37, 'Aquarius'),    # 16°41′7.37″ Aquarius
            'Mars': zodiac_to_longitude(14, 49, 45.03, 'Aries'),       # 14°49′45.03″ Aries
            'Jupiter': zodiac_to_longitude(11, 20, 21.78, 'Pisces'),   # 11°20′21.78″ Pisces
            'Saturn': zodiac_to_longitude(20, 46, 22.21, 'Aries'),     # 20°46′22.21″ Aries
            'Uranus': zodiac_to_longitude(11, 33, 26.03, 'Aquarius'),  # 11°33′26.03″ Aquarius
            'Neptune': zodiac_to_longitude(1, 41, 54.80, 'Aquarius'),  # 1°41′54.80″ Aquarius
            'Pluto': zodiac_to_longitude(8, 1, 9.33, 'Sagittarius'),   # 8°01′9.33″ Sagittarius
            'North Node': zodiac_to_longitude(10, 22, 27.96, 'Virgo'), # 10°22′27.96″ Virgo
            'South Node': zodiac_to_longitude(10, 22, 27.96, 'Pisces'), # 10°22′27.96″ Pisces
            'Chiron': zodiac_to_longitude(0, 0, 0, 'Aries'),           # Placeholder - Chiron not provided
            'Ascendant': zodiac_to_longitude(20, 50, 51.03, 'Virgo'),  # 20°50′51.03″ Virgo
            'MC': zodiac_to_longitude(19, 29, 18.61, 'Gemini'),        # 19°29′18.61″ Gemini
            'Descendant': zodiac_to_longitude(20, 50, 51.03, 'Pisces'), # 20°50′51.03″ Pisces
            'IC': zodiac_to_longitude(19, 29, 18.61, 'Sagittarius'),   # 19°29′18.61″ Sagittarius
        }
    }
}

# Legacy birth data (kept for reference)
NATAL_CHARTS = {
    'christina': {
        'name': 'Christina',
        'date': '1992-03-26',
        'time': '09:04',
        'location': {
            'city': 'Indianapolis',
            'state': 'Indiana',
            'country': 'USA',
            'latitude': 39.7684,
            'longitude': -86.1581,
            'timezone': 'America/Indiana/Indianapolis'
        }
    },
    'julian': {
        'name': 'Julian',
        'date': '2002-02-16',
        'time': '00:30',
        'location': {
            'city': 'Olympia',
            'state': 'Washington',
            'country': 'USA',
            'latitude': 47.0379,
            'longitude': -122.9007,
            'timezone': 'America/Los_Angeles'
        }
    },
    'davison': {
        'name': 'Davison',
        'date': '1997-03-07',
        'time': '03:58',
        'location': {
            'city': 'Lusk',
            'state': 'Wyoming',
            'country': 'USA',
            'latitude': 42.7627,
            'longitude': -104.4522,
            'timezone': 'America/Denver'
        }
    },
    'anna': {
        'name': 'Anna',
        'date': '1992-04-27',
        'time': '21:15',
        'location': {
            'city': 'Seattle',
            'state': 'Washington',
            'country': 'USA',
            'latitude': 47.6062,
            'longitude': -122.3321,
            'timezone': 'America/Los_Angeles'
        }
    },
    'superlunar': {
        'name': 'Superlunar Design Co.',
        'date': '2022-03-01',
        'time': '17:07',
        'location': {
            'city': 'Monterey',
            'state': 'California',
            'country': 'USA',
            'latitude': 36.6002,
            'longitude': -121.8947,
            'timezone': 'America/Los_Angeles'
        }
    },
    'jarrett': {
        'name': 'Jarrett',
        'date': '1998-03-23',
        'time': '17:54',
        'location': {
            'city': 'Indianapolis',
            'state': 'Indiana',
            'country': 'USA',
            'latitude': 39.7684,
            'longitude': -86.1581,
            'timezone': 'America/Indiana/Indianapolis'
        }
    }
}

# Planets to track for transits
PLANETS = {
    'Sun': 0,
    'Moon': 1,
    'Mercury': 2,
    'Venus': 3,
    'Mars': 4,
    'Jupiter': 5,
    'Saturn': 6,
    'Uranus': 7,
    'Neptune': 8,
    'Pluto': 9,
    'North Node': 11,  # True Node (swe.TRUE_NODE = 11, swe.MEAN_NODE = 10)
    'South Node': 11,  # Calculated as North Node + 180 in ephemeris_manager
}

# Aspects to calculate
ASPECTS = {
    'Conjunction': {'angle': 0, 'orb': 3, 'symbol': '☌'},
    'Sextile': {'angle': 60, 'orb': 3, 'symbol': '⚹'},
    'Square': {'angle': 90, 'orb': 3, 'symbol': '□'},
    'Trine': {'angle': 120, 'orb': 3, 'symbol': '△'},
    'Opposition': {'angle': 180, 'orb': 3, 'symbol': '☍'}
}

# Angles
ANGLES = ['Ascendant', 'MC', 'Descendant', 'IC']

# Significance ratings
CRITICAL_TRANSITS = [
    ('Pluto', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
    ('Saturn', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
    ('Uranus', ['Ascendant', 'MC', 'Descendant', 'IC']),
    ('Neptune', ['Ascendant', 'MC', 'Descendant', 'IC']),
    ('Pluto', ['Ascendant', 'MC', 'Descendant', 'IC']),
    ('North Node', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
    ('South Node', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
]

HIGH_TRANSITS = [
    ('Uranus', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
    ('Neptune', ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars']),
    ('Jupiter', ['Sun', 'Moon', 'Venus']),
]

MEDIUM_TRANSITS = [
    ('Jupiter', ['Mercury', 'Mars', 'Ascendant', 'MC']),
    ('Mars', ['Venus']),
    ('Venus', ['Sun', 'Moon', 'Venus', 'Mars']),
]
