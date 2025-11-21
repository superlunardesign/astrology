"""
Configuration for the Transit Tracker application
"""
import os

# Ephemeris path
EPHEMERIS_PATH = os.path.join(os.path.dirname(__file__), '..', 'ephemeris')

# Natal chart data
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
    }
}

# Planets to track
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
    'North Node': 10,  # True Node
    'South Node': 11,  # Calculated as North Node + 180
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
