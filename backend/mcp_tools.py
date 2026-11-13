"""
The tools this app offers over MCP.

Each tool is a plain function over the same engine the web app uses, so an
answer given to a chat assistant is the answer the app would give. Nothing
here knows about transports: the stdio server and the HTTP endpoint both
read this registry.

A tool returns readable text and the structured data behind it. The text is
what an assistant reads back to a person, so it is written the way the app's
copy/paste blocks are - complete sentences of real positions and dates, with
nothing summarised away.
"""
from datetime import datetime

import pytz

from config import ALL_ASPECTS, ASPECTS, MINOR_ASPECTS, NATAL_CHARTS, PLANETS
from progressions import ProgressionCalculator
from sky_search import SIGNS, SkySearch
from transit_calculator import TransitCalculator

DEFAULT_TIMEZONE = 'America/Los_Angeles'

# The engine. The web app shares its own instances with use_engine() so
# that both front doors hit one position cache rather than two.
tc = TransitCalculator()
sky = SkySearch(tc)
pc = ProgressionCalculator(tc)

TOOLS = {}


def use_engine(calculator, progression_calculator=None):
    """Run the tools on an existing calculator instead of our own"""
    global tc, sky, pc
    tc = calculator
    sky = SkySearch(calculator)
    pc = progression_calculator or ProgressionCalculator(calculator)


def today(timezone=DEFAULT_TIMEZONE):
    return datetime.now(pytz.timezone(timezone)).strftime('%Y-%m-%d')


def tool(name, description, schema):
    """Register a tool under its name"""
    def register(handler):
        TOOLS[name] = {
            'name': name,
            'description': description.strip(),
            'inputSchema': schema,
            'handler': handler
        }
        return handler
    return register


def schema(properties, required=None):
    return {
        'type': 'object',
        'properties': properties,
        'required': required or [],
        'additionalProperties': False
    }


# Argument shapes used by several tools
PLANET = {'type': 'string', 'enum': list(PLANETS.keys()),
          'description': 'Transiting body'}
SIGN = {'type': 'string', 'enum': SIGNS}
DATE = {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$',
        'description': 'Date as YYYY-MM-DD'}
CHART = {'type': 'string', 'enum': list(NATAL_CHARTS.keys()),
         'description': 'Which stored chart to read'}
TIMEZONE = {'type': 'string',
            'description': f'IANA timezone for the dates and times in the '
                           f'answer. Defaults to {DEFAULT_TIMEZONE}.'}


def chart_label(chart_key):
    name, _ = tc.get_chart_names(chart_key)
    return name


def lines(*parts):
    return '\n'.join(part for part in parts if part)


# ----------------------------------------------------------------------
# The sky on its own
# ----------------------------------------------------------------------

@tool('sky_on_date', """
Where every planet is at a given moment: sign, degree and whether it is
retrograde. Use this for "where was Mars in March 2019" or "what does the
sky look like tonight". Works for any date the ephemeris covers, past or
future.
""", schema({
    'date': DATE,
    'time': {'type': 'string', 'pattern': r'^\d{2}:\d{2}$',
             'description': '24-hour local time, default 12:00'},
    'planets': {'type': 'array', 'items': PLANET,
                'description': 'Only these bodies. Default: all of them.'},
    'timezone': TIMEZONE
}))
def sky_on_date(date=None, time='12:00', planets=None, timezone=DEFAULT_TIMEZONE):
    date = date or today(timezone)
    positions = sky.sky_on(date, time, timezone, planets)
    label = positions[0]['timezone'] if positions else ''

    return {
        'text': lines(
            f"The sky on {date} at {time} {label}",
            '',
            *[f"  {p['planet']:12} {p['position']}"
              f"{' (Rx)' if p['retrograde'] else ''}" for p in positions]
        ),
        'data': {'date': date, 'time': time, 'positions': positions}
    }


@tool('planet_track', """
Where a planet travelled between two dates: where it started, where it
ended, how much ground it covered, which signs it passed through, and
evenly spaced positions in between. Use this for "where has Pluto been
since 1990" or "how far did Mars move during its retrograde".
""", schema({
    'planet': PLANET,
    'start_date': DATE,
    'end_date': DATE,
    'samples': {'type': 'integer', 'minimum': 2, 'maximum': 200,
                'description': 'How many positions to report along the way '
                               '(default 12)'},
    'timezone': TIMEZONE
}, ['planet', 'start_date', 'end_date']))
def planet_track(planet, start_date, end_date, samples=12, timezone=DEFAULT_TIMEZONE):
    track = sky.track(planet, start_date, end_date, samples, timezone)

    return {
        'text': lines(
            f"{planet} from {start_date} to {end_date}",
            '',
            f"  Started at {track['start']['position']}"
            f"{' retrograde' if track['start']['retrograde'] else ''}",
            f"  Ended at   {track['end']['position']}"
            f"{' retrograde' if track['end']['retrograde'] else ''}",
            f"  Covered    {track['degrees_travelled']}° of actual motion, "
            f"forwards and back",
            f"  Signs      {' -> '.join(track['signs_visited'])}",
            '',
            'Along the way:',
            *[f"  {p['date']}  {p['position']}{' (Rx)' if p['retrograde'] else ''}"
              for p in track['samples']]
        ),
        'data': track
    }


@tool('sign_ingresses', """
Every time a planet changed sign between two dates, including the
retrograde re-entries that make an ingress happen two or three times. Use
this for "when did Pluto enter Aquarius" or "when does Saturn leave
Pisces".
""", schema({
    'planet': PLANET,
    'start_date': DATE,
    'end_date': DATE,
    'timezone': TIMEZONE
}, ['planet', 'start_date', 'end_date']))
def sign_ingresses(planet, start_date, end_date, timezone=DEFAULT_TIMEZONE):
    crossings = sky.ingresses(planet, start_date, end_date, timezone)

    return {
        'text': lines(
            f"{planet} sign changes between {start_date} and {end_date}",
            '',
            *[f"  {c['date']} ~{c['time']} {c['timezone']}  "
              f"{c['left']} -> {c['entered']}"
              f"{' (moving retrograde)' if c['retrograde'] else ''}"
              for c in crossings]
        ) if crossings else
        f"{planet} did not change sign between {start_date} and {end_date}.",
        'data': {'planet': planet, 'ingresses': crossings}
    }


@tool('time_in_sign', """
When a planet was in a particular sign, as dated stretches. A planet that
backs out retrograde and returns gets one stretch per visit. Use this for
"when was Saturn in Aries" or "how long is Jupiter in Leo".
""", schema({
    'planet': PLANET,
    'sign': SIGN,
    'start_date': DATE,
    'end_date': DATE,
    'timezone': TIMEZONE
}, ['planet', 'sign', 'start_date', 'end_date']))
def time_in_sign(planet, sign, start_date, end_date, timezone=DEFAULT_TIMEZONE):
    result = sky.periods_in_sign(planet, sign, start_date, end_date, timezone)

    def describe(period):
        start = period['from'].get('date')
        end = period['to'].get('date')
        text = f"  {start} to {end}"
        edges = []
        if period.get('from_edge'):
            edges.append(f"began {period['from_edge']}")
        if period.get('to_edge'):
            edges.append(f"still there {period['to_edge']}")
        if period.get('entered_retrograde'):
            edges.append('entered retrograde')
        if period.get('left_retrograde'):
            edges.append('left retrograde')
        return text + (f"  ({'; '.join(edges)})" if edges else '')

    return {
        'text': lines(
            f"{planet} in {result['sign']}, searched {start_date} to {end_date}",
            '',
            *[describe(p) for p in result['periods']]
        ) if result['periods'] else
        f"{planet} was not in {result['sign']} at any point between "
        f"{start_date} and {end_date}.",
        'data': result
    }


@tool('retrograde_periods', """
Every retrograde stretch between two dates: the day it stationed
retrograde, the day it stationed direct, the degrees it covered going
back, and how long it lasted. A retrograde already under way when the
window opens is reported from the day it really began.
""", schema({
    'planet': PLANET,
    'start_date': DATE,
    'end_date': DATE,
    'timezone': TIMEZONE
}, ['planet', 'start_date', 'end_date']))
def retrograde_periods(planet, start_date, end_date, timezone=DEFAULT_TIMEZONE):
    result = sky.retrograde_periods(planet, start_date, end_date, timezone)

    def describe(period):
        if not period['ends']:
            return (f"  {period['begins']['date']} went retrograde at "
                    f"{period['begins']['position']} - still retrograde at "
                    f"{end_date}")
        return (f"  {period['begins']['date']} to {period['ends']['date']}  "
                f"{period['begins']['position']} back to "
                f"{period['ends']['position']}  "
                f"({period['days']} days, {period['travelled_back']}°)")

    if result.get('note'):
        return {'text': result['note'], 'data': result}

    return {
        'text': lines(
            f"{planet} retrograde between {start_date} and {end_date}",
            '',
            *[describe(p) for p in result['periods']]
        ) if result['periods'] else
        f"{planet} was not retrograde at any point between {start_date} "
        f"and {end_date}.",
        'data': result
    }


@tool('stations', """
Every time a planet turned around between two dates - stationed retrograde
or stationed direct - and the exact degree it turned at.
""", schema({
    'planet': PLANET,
    'start_date': DATE,
    'end_date': DATE,
    'timezone': TIMEZONE
}, ['planet', 'start_date', 'end_date']))
def stations(planet, start_date, end_date, timezone=DEFAULT_TIMEZONE):
    found = sky.stations(planet, start_date, end_date, timezone)

    return {
        'text': lines(
            f"{planet} stations between {start_date} and {end_date}",
            '',
            *[f"  {s['date']} ~{s['time']} {s['timezone']}  {s['station']} "
              f"at {s['position']}" for s in found]
        ) if found else
        f"{planet} did not station between {start_date} and {end_date}.",
        'data': {'planet': planet, 'stations': found}
    }


@tool('degree_crossings', """
Every time a planet reached an exact degree of the zodiac between two
dates - or an exact aspect to that degree. Use this for a placement the
app does not store: "when does Saturn conjoin 15 degrees Aries", "when
did Jupiter trine 2 degrees Scorpio". Perfection is the 0°00' crossing, so
a planet that stations just short is correctly reported as never reaching
it.
""", schema({
    'planet': PLANET,
    'sign': SIGN,
    'degree': {'type': 'number', 'minimum': 0, 'exclusiveMaximum': 30,
               'description': 'Degree within the sign, 0 to 29.99'},
    'start_date': DATE,
    'end_date': DATE,
    'aspect': {'type': 'string', 'enum': list(ALL_ASPECTS.keys()),
               'description': 'Default Conjunction'},
    'timezone': TIMEZONE
}, ['planet', 'sign', 'degree', 'start_date', 'end_date']))
def degree_crossings(planet, sign, degree, start_date, end_date,
                     aspect='Conjunction', timezone=DEFAULT_TIMEZONE):
    result = sky.degree_crossings(planet, sign, degree, start_date, end_date,
                                  aspect, timezone)
    word = tc.get_aspect_word(aspect)

    return {
        'text': lines(
            f"{planet} {word} {result['target']}, between {start_date} "
            f"and {end_date}",
            '',
            *[f"  {c['date']} ~{c['time']} {c['timezone']}"
              f"{' (Rx)' if c['retrograde'] else ''}"
              f"{'  ' + planet + ' at ' + c['position'] if c['position'] else ''}"
              for c in result['crossings']]
        ) if result['crossings'] else
        f"{planet} never went exactly {word} {result['target']} between "
        f"{start_date} and {end_date}.",
        'data': result
    }


# ----------------------------------------------------------------------
# Stored charts
# ----------------------------------------------------------------------

@tool('list_charts', """
The charts this app holds, with their birth data. Call this first if you
are unsure which chart key to use.
""", schema({}))
def list_charts():
    charts = []
    for key, chart in NATAL_CHARTS.items():
        name, short_name = tc.get_chart_names(key)
        charts.append({
            'key': key, 'name': name, 'short_name': short_name,
            'date': chart['date'], 'time': chart['time'],
            'location': chart['location'].get('name',
                                              chart['location'].get('timezone'))
        })

    return {
        'text': lines(
            'Charts available:',
            '',
            *[f"  {c['key']:12} {c['name']} - born {c['date']} {c['time']}, "
              f"{c['location']}" for c in charts]
        ),
        'data': {'charts': charts}
    }


@tool('natal_chart', """
A stored chart's own placements: every planet with its sign, degree and
house, the twelve house cusps, and each house's ruler and where that ruler
sits. This is the chart itself, not what is transiting it.
""", schema({'chart': CHART}, ['chart']))
def natal_chart(chart):
    return {
        'text': '\n'.join(tc.format_natal_reference(chart)),
        'data': tc.natal_reference(chart)
    }


@tool('transits_on_date', """
Every transit to a stored chart on one day, with its orb, whether it is
applying or separating, when it last perfected and when it next will, and
where in the zodiac it perfects. This is the app's daily reading.
""", schema({
    'chart': CHART,
    'date': DATE,
    'time': {'type': 'string', 'pattern': r'^\d{2}:\d{2}$',
             'description': '24-hour local time, default 12:00'},
    'max_orb': {'type': 'number', 'minimum': 0.1, 'maximum': 10,
                'description': 'Widest orb to include, in degrees. Default 3.'},
    'include_minor': {'type': 'boolean',
                      'description': 'Include semisextiles, quincunxes and the '
                                     'other minor aspects. Default false.'},
    'include_natal': {'type': 'boolean',
                      'description': 'Prepend the chart\'s own placements. '
                                     'Default true.'},
    'timezone': TIMEZONE
}, ['chart']))
def transits_on_date(chart, date=None, time='12:00', max_orb=3,
                     include_minor=False, include_natal=True,
                     timezone=DEFAULT_TIMEZONE):
    date = date or today(timezone)
    result = tc.get_daily_dashboard(chart, date, max_orb=max_orb, time_str=time,
                                    timezone=timezone, include_minor=include_minor,
                                    include_natal=include_natal)
    return {
        'text': result['plain_text'],
        'data': {'chart': chart, 'date': date,
                 'total_aspects': result['total_aspects'],
                 'aspects': result['aspects']}
    }


@tool('transit_timeline', """
One transit followed from start to finish: the dates it came within 5°, 3°
and 1°, every date it perfects (a retrograde gives three), any station in
between, and the dates it leaves orb again. Use this when someone asks how
long a transit lasts or when it is strongest.
""", schema({
    'chart': CHART,
    'transit_planet': PLANET,
    'natal_point': {'type': 'string',
                    'enum': list(PLANETS.keys()) +
                            ['Ascendant', 'MC', 'Descendant', 'IC'],
                    'description': 'The natal placement being aspected'},
    'aspect': {'type': 'string', 'enum': list(ALL_ASPECTS.keys())},
    'date': DATE,
    'timezone': TIMEZONE
}, ['chart', 'transit_planet', 'natal_point', 'aspect']))
def transit_timeline(chart, transit_planet, natal_point, aspect, date=None,
                     timezone=DEFAULT_TIMEZONE):
    date = date or today(timezone)
    timeline = tc.calculate_aspect_timeline(chart, transit_planet, natal_point,
                                            aspect, date, precise=True)
    word = tc.get_aspect_word(aspect)
    header = (f"{transit_planet} {word} {chart_label(chart)}'s natal "
              f"{natal_point}, around {date}")

    def date_line(label, value):
        return f"  {label:22} {value}" if value else None

    exacts = timeline.get('exact_dates') or []
    return {
        'text': lines(
            header,
            '',
            date_line('Enters 5° orb', timeline.get('enter_5deg')),
            date_line('Enters 3° orb', timeline.get('enter_3deg')),
            date_line('Enters 1° orb', timeline.get('enter_1deg')),
            ('  Exact                  ' + ', '.join(
                f"{hit['date']}{' (Rx)' if hit.get('retrograde') else ''}"
                for hit in exacts)) if exacts else
            '  Never reaches 0°00\' in this window',
            *[f"  Station                {s['type']} on {s['date']}"
              for s in (timeline.get('stations') or [])],
            date_line('Leaves 1° orb', timeline.get('leave_1deg')),
            date_line('Leaves 3° orb', timeline.get('leave_3deg')),
            date_line('Leaves 5° orb', timeline.get('leave_5deg'))
        ),
        'data': timeline
    }


@tool('scan_transits', """
Every transit that perfects to a stored chart between two dates, in date
order. Use this for "what is coming up for me this spring" or to find a
particular aspect's date without knowing roughly when it falls.
""", schema({
    'chart': CHART,
    'start_date': DATE,
    'end_date': DATE,
    'planets': {'type': 'array', 'items': PLANET,
                'description': 'Only these transiting bodies. Default: all.'},
    'aspects': {'type': 'array',
                'items': {'type': 'string', 'enum': list(ALL_ASPECTS.keys())},
                'description': 'Only these aspects. Default: the major five.'},
    'include_minor': {'type': 'boolean', 'description': 'Default false.'}
}, ['chart', 'start_date', 'end_date']))
def scan_transits(chart, start_date, end_date, planets=None, aspects=None,
                  include_minor=False):
    hits = tc.scan_future_transits(chart, start_date, end_date,
                                   transit_planets=planets, aspect_types=aspects,
                                   include_minor=include_minor)

    def describe(hit):
        word = tc.get_aspect_word(hit['aspect'])
        marker = ' (Rx)' if hit.get('exact_retrograde') else ''
        return (f"  {hit['exact_date']}  {hit['transit_planet']}{marker} {word} "
                f"natal {hit['natal_point']}")

    return {
        'text': lines(
            f"Transits perfecting for {chart_label(chart)} between "
            f"{start_date} and {end_date}",
            '',
            *[describe(hit) for hit in hits]
        ) if hits else
        f"Nothing perfects for {chart_label(chart)} between {start_date} "
        f"and {end_date}.",
        'data': {'chart': chart, 'count': len(hits), 'transits': hits}
    }


@tool('transit_journal', """
A day-by-day reading for a stored chart: what the Moon does each day, where
the planets sit, and which transits are active, for up to 30 days. This is
the long-form daily writeup, not a summary.
""", schema({
    'chart': CHART,
    'start_date': DATE,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 30,
             'description': 'Default 7, at most 30'},
    'include_minor': {'type': 'boolean', 'description': 'Default false.'},
    'include_natal': {'type': 'boolean', 'description': 'Default true.'},
    'timezone': TIMEZONE
}, ['chart']))
def transit_journal(chart, start_date=None, days=7, include_minor=False,
                    include_natal=True, timezone=DEFAULT_TIMEZONE):
    start_date = start_date or today(timezone)
    journal = tc.generate_transit_journal(chart, start_date, days=days,
                                          timezone=timezone,
                                          include_minor=include_minor,
                                          include_natal=include_natal)
    return {
        'text': journal['plain_text'],
        'data': {'chart': chart, 'start_date': start_date, 'days': days}
    }


@tool('progressions', """
A stored chart's secondary progressions and solar arc directions for a
date: the progressed positions, the arc, and the aspects the progressed
and directed points make to the natal chart and to each other, with the
dates they perfect.
""", schema({
    'chart': CHART,
    'date': DATE,
    'orb': {'type': 'number', 'minimum': 0.1, 'maximum': 3,
            'description': 'Widest orb to include, in degrees. Default 1.'},
    'include_minor': {'type': 'boolean', 'description': 'Default false.'},
    'timezone': TIMEZONE
}, ['chart']))
def progressions(chart, date=None, orb=1.0, include_minor=False,
                 timezone=DEFAULT_TIMEZONE):
    date = date or today(timezone)
    report = pc.generate_report(chart, date, orb=orb, timezone=timezone,
                                include_minor=include_minor)
    return {
        'text': report['plain_text'],
        'data': {'chart': chart, 'date': date,
                 'years_elapsed': report['years_elapsed'],
                 'aspects': report['aspects']}
    }


# ----------------------------------------------------------------------
# search / fetch, which some assistants require before they will connect
# ----------------------------------------------------------------------

def catalogue():
    """Everything search can turn up, as documents with ids"""
    now = today()
    entries = [{
        'id': f'sky:{now}',
        'title': f'The sky on {now}',
        'text': 'Every planet\'s sign, degree and direction today',
        'keywords': ['sky', 'today', 'positions', 'planets', 'transits', 'now']
    }]

    for key in NATAL_CHARTS:
        name, short_name = tc.get_chart_names(key)
        entries.append({
            'id': f'natal:{key}',
            'title': f'{name} - natal chart',
            'text': f'Placements, house cusps and house rulers for {name}',
            'keywords': [key, name.lower(), short_name.lower(), 'natal',
                         'chart', 'placements', 'houses']
        })
        entries.append({
            'id': f'transits:{key}:{now}',
            'title': f'{name} - transits on {now}',
            'text': f'Every transit to {name} today, with its orb and '
                    f'exact dates',
            'keywords': [key, name.lower(), short_name.lower(), 'transits',
                         'today', 'reading']
        })
        entries.append({
            'id': f'progressions:{key}:{now}',
            'title': f'{name} - progressions and solar arc on {now}',
            'text': f'Secondary progressions and solar arc directions for {name}',
            'keywords': [key, name.lower(), short_name.lower(), 'progressions',
                         'progressed', 'solar arc', 'directions']
        })

    return entries


@tool('search', """
Find readings this server can produce for a search phrase. Returns
documents with ids to pass to fetch. For anything with a date, a range or a
planet in it, the other tools answer better and more precisely than this
one does.
""", schema({'query': {'type': 'string', 'description': 'What to look for'}},
            ['query']))
def search(query):
    words = [word for word in str(query).lower().split() if word]
    scored = []

    for entry in catalogue():
        haystack = ' '.join([entry['title'].lower(), entry['text'].lower(),
                             ' '.join(entry['keywords'])])
        score = sum(1 for word in words if word in haystack)
        if score:
            scored.append((score, entry))

    scored.sort(key=lambda pair: -pair[0])
    results = [{'id': entry['id'], 'title': entry['title'],
                'url': f"astrology://{entry['id']}"}
               for _, entry in scored] or \
              [{'id': entry['id'], 'title': entry['title'],
                'url': f"astrology://{entry['id']}"}
               for entry in catalogue()]

    return {'json': {'results': results},
            'data': {'results': results}}


@tool('fetch', """
Retrieve one of the documents search returned, by its id.
""", schema({'id': {'type': 'string', 'description': 'Document id from search'}},
            ['id']))
def fetch(id):
    kind, _, rest = str(id).partition(':')
    chart, _, date = rest.partition(':')

    if kind == 'sky':
        body = sky_on_date(date=chart or None)['text']
        title = f'The sky on {chart}'
    elif kind == 'natal':
        body = natal_chart(chart)['text']
        title = f'{chart_label(chart)} - natal chart'
    elif kind == 'transits':
        body = transits_on_date(chart, date or None)['text']
        title = f'{chart_label(chart)} - transits on {date}'
    elif kind == 'progressions':
        body = progressions(chart, date or None)['text']
        title = f'{chart_label(chart)} - progressions on {date}'
    else:
        raise ValueError(f"'{id}' is not a document id. Call search first.")

    document = {'id': id, 'title': title, 'text': body,
                'url': f'astrology://{id}', 'metadata': None}
    return {'json': document, 'data': document}


def list_tools():
    """The tool definitions, without the handlers"""
    return [{key: tool[key] for key in ('name', 'description', 'inputSchema')}
            for tool in TOOLS.values()]


def call_tool(name, arguments):
    """
    Run a tool and return MCP content blocks.

    Anything the tool raises comes back as an error result rather than an
    exception, because a chat assistant can act on "that is not a sign" and
    cannot act on a dropped connection.
    """
    if name not in TOOLS:
        return {'content': [{'type': 'text', 'text': f"No tool named '{name}'."}],
                'isError': True}

    try:
        result = TOOLS[name]['handler'](**(arguments or {}))
    except TypeError as error:
        return {'content': [{'type': 'text',
                             'text': f"{name}: {error}"}], 'isError': True}
    except Exception as error:
        return {'content': [{'type': 'text',
                             'text': f"{name} failed: {error}"}], 'isError': True}

    if 'json' in result:
        # search and fetch answer in JSON, which is what the assistants that
        # require those two tools expect to parse
        import json
        return {'content': [{'type': 'text',
                             'text': json.dumps(result['json'])}],
                'structuredContent': result['json']}

    content = [{'type': 'text', 'text': result['text']}]
    response = {'content': content}
    if result.get('data') is not None:
        response['structuredContent'] = {'result': result['data']}
    return response
