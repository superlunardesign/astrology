"""
Secondary progressions and solar arc directions

Both techniques move a chart forward at the rate of one day of ephemeris per
year of life. Secondary progressions read that day directly - the progressed
Moon covers about a degree a month, the progressed Sun about a degree a year.
Solar arc takes the distance the progressed Sun has travelled and advances
every natal point by that same arc.

Exactness works the same way it does for transits: an aspect is exact at the
moment it reaches 0°00', found as a real crossing rather than a tightest orb.
That matters more here than it does for transits, because progressed Mercury,
Venus and Mars do station - a progressed planet can approach an aspect, turn,
and never perfect it.
"""
from datetime import datetime, timedelta

from config import ASPECTS, NATAL_CHARTS, NATAL_POSITIONS, PLANETS

# The year the day-for-a-year rate is measured in
TROPICAL_YEAR_DAYS = 365.242190

# The Sun's mean daily motion, which is the Naibod rate per year of life
NAIBOD_DEGREES_PER_YEAR = 0.9856473

# Progressions and directions move slowly, so they are read on a tight orb.
# At a degree a year, solar arc within 1° is already about a year either side.
DEFAULT_ORB = 1.0

ASPECT_POINTS = list(PLANETS.keys()) + ['Ascendant', 'MC', 'Descendant', 'IC']

# What gets progressed. The nodes and angles are handled separately.
PROGRESSED_BODIES = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                     'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']

MOON_PHASES = [
    (0, 'New'), (45, 'Crescent'), (90, 'First Quarter'), (135, 'Gibbous'),
    (180, 'Full'), (225, 'Disseminating'), (270, 'Last Quarter'), (315, 'Balsamic')
]


class ProgressionCalculator:
    """Secondary progressions and solar arc directions for a chart"""

    def __init__(self, transit_calculator, angle_method='solar_arc'):
        """
        Args:
            transit_calculator: shares its ephemeris, chart data and the
                                crossing engine that finds exact dates
            angle_method: how the progressed MC and Ascendant advance -
                          'solar_arc' or 'naibod'. Directed angles are always
                          natal plus the arc, so the choice only affects
                          progressions.
        """
        self.tc = transit_calculator
        self.em = transit_calculator.em
        self.ncm = transit_calculator.ncm
        self.angle_method = angle_method

    # ------------------------------------------------------------------
    # The day-for-a-year clock
    # ------------------------------------------------------------------

    def birth_julian_day(self, chart_key):
        """Julian Day of the chart's own moment"""
        birth = NATAL_CHARTS[chart_key]
        return self.em.get_julian_day(birth['date'], birth['time'],
                                      birth['location']['timezone'])

    def years_elapsed(self, chart_key, jd):
        """Tropical years between the chart's moment and a calendar Julian Day"""
        return (jd - self.birth_julian_day(chart_key)) / TROPICAL_YEAR_DAYS

    def progressed_julian_day(self, chart_key, jd):
        """
        The ephemeris moment a calendar date reads from.

        One day of ephemeris per year of life, so a 34 year old's progressed
        chart is the sky 34 days after they were born.
        """
        return self.birth_julian_day(chart_key) + self.years_elapsed(chart_key, jd)

    def progressed_body(self, chart_key, planet):
        """
        A progressed planet as a function of calendar Julian Day.

        Handed to the crossing engine, which then finds exact dates for
        progressions exactly as it does for transits.
        """
        def position_at(jd):
            return self.em.get_planet_position(
                planet, self.progressed_julian_day(chart_key, jd))

        return position_at

    def natal_longitude(self, chart_key, point):
        """The stored natal degree - the chart as its owner has it"""
        return NATAL_POSITIONS[chart_key]['positions'][point]['longitude'] \
            if isinstance(NATAL_POSITIONS[chart_key]['positions'][point], dict) \
            else NATAL_POSITIONS[chart_key]['positions'][point]

    # ------------------------------------------------------------------
    # Solar arc
    # ------------------------------------------------------------------

    def solar_arc_at(self, chart_key, jd):
        """
        How far the progressed Sun has moved from its natal place.

        This is the arc every natal point is directed by, so the directed Sun
        always lands exactly on the progressed Sun.
        """
        progressed_sun = self.em.get_planet_position(
            'Sun', self.progressed_julian_day(chart_key, jd))['longitude']

        return (progressed_sun - self.natal_longitude(chart_key, 'Sun')) % 360

    def directed_body(self, chart_key, point):
        """A solar arc directed natal point as a function of calendar Julian Day"""
        natal_long = self.natal_longitude(chart_key, point)

        def position_at(jd):
            arc = self.solar_arc_at(chart_key, jd)
            # Everything is carried by the Sun, so it moves at the Sun's pace
            speed = self.em.get_planet_position(
                'Sun', self.progressed_julian_day(chart_key, jd))['speed']
            return {'longitude': (natal_long + arc) % 360, 'speed': speed}

        return position_at

    # ------------------------------------------------------------------
    # Charts for a date
    # ------------------------------------------------------------------

    def _describe(self, chart_key, longitude, speed=None):
        return {
            'longitude': longitude,
            'sign': self.tc.get_sign_from_longitude(longitude),
            'degree': int(longitude % 30),
            'minute': int(((longitude % 30) % 1) * 60),
            'house': self.ncm.get_house_for_longitude(chart_key, longitude),
            'retrograde': bool(speed is not None and speed < 0)
        }

    def progressed_chart(self, chart_key, date_str, timezone='America/Los_Angeles'):
        """Every progressed position for a calendar date"""
        jd = self.em.get_julian_day(date_str, '12:00', timezone)
        progressed_jd = self.progressed_julian_day(chart_key, jd)

        positions = {}
        for planet in PROGRESSED_BODIES:
            position = self.em.get_planet_position(planet, progressed_jd)
            positions[planet] = self._describe(chart_key, position['longitude'],
                                               position['speed'])

        # The angles have no single agreed method, so they follow the setting
        if self.angle_method == 'naibod':
            angle_arc = NAIBOD_DEGREES_PER_YEAR * self.years_elapsed(chart_key, jd)
        else:
            angle_arc = self.solar_arc_at(chart_key, jd)

        for angle in ['Ascendant', 'MC', 'Descendant', 'IC']:
            longitude = (self.natal_longitude(chart_key, angle) + angle_arc) % 360
            positions[angle] = self._describe(chart_key, longitude)

        return {
            'date': date_str,
            'progressed_julian_day': progressed_jd,
            'years_elapsed': self.years_elapsed(chart_key, jd),
            'angle_method': self.angle_method,
            'angle_arc': angle_arc,
            'positions': positions
        }

    def directed_chart(self, chart_key, date_str, timezone='America/Los_Angeles'):
        """Every natal point advanced by the solar arc"""
        jd = self.em.get_julian_day(date_str, '12:00', timezone)
        arc = self.solar_arc_at(chart_key, jd)

        positions = {}
        for point in ASPECT_POINTS:
            if point not in NATAL_POSITIONS[chart_key]['positions']:
                continue
            longitude = (self.natal_longitude(chart_key, point) + arc) % 360
            positions[point] = self._describe(chart_key, longitude)

        return {'date': date_str, 'arc': arc, 'positions': positions}

    # ------------------------------------------------------------------
    # Aspects, with real exact dates
    # ------------------------------------------------------------------

    # How far to look for a perfection, and how finely, by how fast the point
    # moves in calendar time. The progressed Moon covers a degree a month; a
    # progressed outer planet covers a degree in a century, so its hits are
    # decades away when they exist at all.
    SEARCH_WINDOWS = {
        'Moon': (6, 2),
        'Sun': (20, 10), 'Mercury': (20, 10), 'Venus': (20, 10), 'Mars': (20, 10),
        'Jupiter': (60, 30), 'Saturn': (60, 30), 'Uranus': (60, 30),
        'Neptune': (60, 30), 'Pluto': (60, 30),
        'directed': (25, 30),
    }

    def _exact_dates(self, chart_key, body, target_long, aspect_angle, date_str,
                     window_years=4, step_days=7, timezone='America/Los_Angeles'):
        """
        When a progressed or directed aspect actually reaches 0°00'.

        Returns the pass behind and the pass ahead, either of which may be
        absent - a progressed planet that stations short of an aspect never
        perfects it, the same way a transiting one doesn't.
        """
        reference = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=12)
        span = timedelta(days=365.25 * window_years)

        # A progressed chart does not exist before the chart does, so the pass
        # behind us is only looked for back as far as the birth moment
        birth = NATAL_CHARTS[chart_key]
        birth_dt = datetime.strptime(f"{birth['date']} {birth['time']}", '%Y-%m-%d %H:%M')
        earliest = max(reference - span, birth_dt)

        previous = self.tc.find_exact_crossings(
            body, target_long, aspect_angle, earliest, reference,
            step_hours=step_days * 24, timezone=timezone,
            max_results=1, newest_first=True
        )
        upcoming = self.tc.find_exact_crossings(
            body, target_long, aspect_angle, reference, reference + span,
            step_hours=step_days * 24, timezone=timezone, max_results=1
        )

        def describe(hit):
            return {
                'date': hit['datetime'].strftime('%Y-%m-%d'),
                'retrograde': hit['retrograde']
            }

        return (describe(previous[-1]) if previous else None,
                describe(upcoming[0]) if upcoming else None)

    def find_aspects(self, chart_key, date_str, orb=DEFAULT_ORB,
                     timezone='America/Los_Angeles'):
        """
        Progressed to natal, progressed to progressed, and directed to natal.

        Each aspect carries the pass behind it and the pass ahead, so a
        progressed aspect that has already perfected reads differently from one
        still coming.
        """
        progressed = self.progressed_chart(chart_key, date_str, timezone)
        directed = self.directed_chart(chart_key, date_str, timezone)

        found = {'progressed_to_natal': [], 'progressed_to_progressed': [],
                 'directed_to_natal': []}

        natal_points = [p for p in ASPECT_POINTS
                        if p in NATAL_POSITIONS[chart_key]['positions']]

        def add(bucket, moving_name, moving, target_name, target_long,
                aspect_name, aspect_data, body, window):
            aspect_orb = self.tc.calculate_aspect_orb(
                moving['longitude'], target_long, aspect_data['angle'])
            if aspect_orb > orb:
                return

            window_years, sample_days = window
            previous_exact, next_exact = self._exact_dates(
                chart_key, body, target_long, aspect_data['angle'], date_str,
                window_years=window_years, step_days=sample_days, timezone=timezone)

            found[bucket].append({
                'search_window_years': window_years,
                'moving_point': moving_name,
                'moving_sign': moving['sign'],
                'moving_degree': moving['degree'],
                'moving_minute': moving['minute'],
                'retrograde': moving['retrograde'],
                'target_point': target_name,
                'target_sign': self.tc.get_sign_from_longitude(target_long),
                'aspect': aspect_name,
                'aspect_word': self.tc.get_aspect_word(aspect_name),
                'orb': aspect_orb,
                'previous_exact': previous_exact,
                'next_exact': next_exact
            })

        for planet in PROGRESSED_BODIES:
            moving = progressed['positions'][planet]
            body = self.progressed_body(chart_key, planet)
            window = self.SEARCH_WINDOWS[planet]

            for point in natal_points:
                target_long = self.natal_longitude(chart_key, point)
                for aspect_name, aspect_data in ASPECTS.items():
                    add('progressed_to_natal', planet, moving, point, target_long,
                        aspect_name, aspect_data, body, window)

        # Progressed to progressed: the progressed Moon against the rest is
        # where this mostly lives, so only it moves fast enough to matter
        moon = progressed['positions']['Moon']
        moon_body = self.progressed_body(chart_key, 'Moon')
        for planet in PROGRESSED_BODIES:
            if planet == 'Moon':
                continue
            target_long = progressed['positions'][planet]['longitude']
            for aspect_name, aspect_data in ASPECTS.items():
                add('progressed_to_progressed', 'Moon', moon, planet, target_long,
                    aspect_name, aspect_data, moon_body, self.SEARCH_WINDOWS['Moon'])

        for point in natal_points:
            moving = directed['positions'][point]
            body = self.directed_body(chart_key, point)
            for target in natal_points:
                target_long = self.natal_longitude(chart_key, target)
                for aspect_name, aspect_data in ASPECTS.items():
                    add('directed_to_natal', point, moving, target, target_long,
                        aspect_name, aspect_data, body, self.SEARCH_WINDOWS['directed'])

        for bucket in found.values():
            bucket.sort(key=lambda item: item['orb'])

        return found

    # ------------------------------------------------------------------
    # The progressed lunation cycle
    # ------------------------------------------------------------------

    def progressed_moon_cycle(self, chart_key, date_str,
                              timezone='America/Los_Angeles'):
        """
        Where the progressed Moon is in its cycle with the progressed Sun, and
        when it next changes sign or phase. The whole cycle runs about 30
        years, so these are the long markers.
        """
        jd = self.em.get_julian_day(date_str, '12:00', timezone)
        progressed_jd = self.progressed_julian_day(chart_key, jd)

        moon = self.em.get_planet_position('Moon', progressed_jd)['longitude']
        sun = self.em.get_planet_position('Sun', progressed_jd)['longitude']
        separation = (moon - sun) % 360

        phase = MOON_PHASES[0][1]
        for boundary, name in MOON_PHASES:
            if separation >= boundary:
                phase = name

        reference = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=12)
        moon_body = self.progressed_body(chart_key, 'Moon')

        # Next sign change: the next time it crosses a 30° boundary
        next_sign = None
        boundary = (int(moon / 30) + 1) * 30 % 360
        crossings = self.tc.find_exact_crossings(
            moon_body, boundary, 0, reference, reference + timedelta(days=365.25 * 4),
            step_hours=48, timezone=timezone, max_results=1)
        if crossings:
            next_sign = {
                'date': crossings[0]['datetime'].strftime('%Y-%m-%d'),
                'sign': self.tc.get_sign_from_longitude(boundary)
            }

        # Next phase: the next time the Moon-Sun separation reaches the next
        # eighth of the cycle
        next_phase = None
        next_boundary = next((b for b, _ in MOON_PHASES if b > separation), 360)
        next_phase_name = next((n for b, n in MOON_PHASES if b > separation), 'New')

        def separation_body(jd_value):
            moment = self.progressed_julian_day(chart_key, jd_value)
            moon_position = self.em.get_planet_position('Moon', moment)
            sun_position = self.em.get_planet_position('Sun', moment)
            return {
                'longitude': (moon_position['longitude'] - sun_position['longitude']) % 360,
                'speed': moon_position['speed'] - sun_position['speed']
            }

        phase_crossings = self.tc.find_exact_crossings(
            separation_body, next_boundary % 360, 0, reference,
            reference + timedelta(days=365.25 * 6), step_hours=48,
            timezone=timezone, max_results=1)
        if phase_crossings:
            next_phase = {
                'date': phase_crossings[0]['datetime'].strftime('%Y-%m-%d'),
                'phase': next_phase_name
            }

        return {
            'sign': self.tc.get_sign_from_longitude(moon),
            'degree': int(moon % 30),
            'minute': int(((moon % 30) % 1) * 60),
            'house': self.ncm.get_house_for_longitude(chart_key, moon),
            'separation_from_sun': separation,
            'phase': phase,
            'next_sign_change': next_sign,
            'next_phase': next_phase
        }

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def generate_report(self, chart_key, date_str, orb=DEFAULT_ORB,
                        timezone='America/Los_Angeles'):
        """Progressions and directions for one date, with copy/paste text"""
        progressed = self.progressed_chart(chart_key, date_str, timezone)
        directed = self.directed_chart(chart_key, date_str, timezone)
        aspects = self.find_aspects(chart_key, date_str, orb, timezone)
        moon = self.progressed_moon_cycle(chart_key, date_str, timezone)

        chart_name, chart_short_name = self.tc.get_chart_names(chart_key)

        return {
            'chart': chart_key,
            'chart_name': chart_name,
            'date': date_str,
            'orb': orb,
            'years_elapsed': progressed['years_elapsed'],
            'progressed': progressed,
            'directed': directed,
            'progressed_moon': moon,
            'aspects': aspects,
            'plain_text': self._generate_plain_text(
                chart_name, chart_short_name, date_str, orb,
                progressed, directed, moon, aspects)
        }

    def _generate_plain_text(self, chart_name, chart_short_name, date_str, orb,
                             progressed, directed, moon, aspects):
        formatted_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y')

        def position_line(name, position):
            marker = ' (Rx)' if position['retrograde'] else ''
            return (f"  {name:12} - {position['degree']:2d}°{position['minute']:02d}' "
                    f"{position['sign']}{marker} (House {position['house']})")

        def aspect_line(item):
            marker = ' (Rx)' if item['retrograde'] else ''
            line = (f"  {item['moving_point']}{marker} at "
                    f"{item['moving_degree']}°{item['moving_minute']:02d}' {item['moving_sign']} "
                    f"{item['aspect_word']} {item['target_point']} in {item['target_sign']} "
                    f"at {self.tc.format_orb(item['orb'])}")

            if item['previous_exact']:
                line += f" | was exact {self._format_date(item['previous_exact']['date'])}"
            if item['next_exact']:
                label = 'next exact' if item['previous_exact'] else 'exact'
                line += f" | {label} {self._format_date(item['next_exact']['date'])}"
            if not item['previous_exact'] and not item['next_exact']:
                line += f" | no exact hit within {item['search_window_years']} yrs"

            return line

        arc_degrees = int(directed['arc'])
        arc_minutes = int((directed['arc'] % 1) * 60)

        lines = [
            f"PROGRESSIONS & SOLAR ARC - {chart_name}",
            f"For {formatted_date}  |  {progressed['years_elapsed']:.2f} years of life",
            f"Solar arc: {arc_degrees}°{arc_minutes:02d}'  |  aspects within {orb:g}°",
            "",
            "=" * 50,
            "PROGRESSED CHART",
            "=" * 50,
            "",
        ]

        for planet in PROGRESSED_BODIES:
            lines.append(position_line(planet, progressed['positions'][planet]))

        lines.append("")
        lines.append(f"Angles by {progressed['angle_method'].replace('_', ' ')}:")
        for angle in ['Ascendant', 'MC', 'Descendant', 'IC']:
            lines.append(position_line(angle, progressed['positions'][angle]))

        lines += [
            "",
            "=" * 50,
            "PROGRESSED MOON",
            "=" * 50,
            "",
            f"  {moon['degree']}°{moon['minute']:02d}' {moon['sign']} (House {moon['house']})",
            f"  Phase: {moon['phase']} "
            f"({int(moon['separation_from_sun'])}° from the progressed Sun)",
        ]
        if moon['next_sign_change']:
            lines.append(f"  Enters {moon['next_sign_change']['sign']} on "
                         f"{self._format_date(moon['next_sign_change']['date'])}")
        if moon['next_phase']:
            lines.append(f"  {moon['next_phase']['phase']} phase begins "
                         f"{self._format_date(moon['next_phase']['date'])}")

        for title, bucket, empty in [
            (f"PROGRESSED TO {chart_short_name.upper()}'S NATAL CHART",
             'progressed_to_natal', 'No progressed aspects within orb'),
            ("PROGRESSED MOON TO PROGRESSED CHART",
             'progressed_to_progressed', 'No progressed-to-progressed aspects within orb'),
            (f"SOLAR ARC DIRECTED TO {chart_short_name.upper()}'S NATAL CHART",
             'directed_to_natal', 'No directed aspects within orb'),
        ]:
            lines += ["", "=" * 50, title, "=" * 50, ""]
            items = aspects[bucket]
            lines += [aspect_line(item) for item in items] if items else [f"  {empty}"]

        return "\n".join(lines)

    def _format_date(self, date_str):
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%b %d, %Y')
