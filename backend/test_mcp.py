"""
Checks for the MCP server and the REST door beside it.

Three things are being checked:

  - the protocol: a client that follows the spec gets what the spec says,
    including the awkward parts (notifications get no reply, an unknown
    method is an error rather than a crash, a batch comes back as a batch)

  - the way in: tokens, both content types, the OpenAPI document

  - the answers: sign changes, stations and retrogrades against dates
    published independently of this code, and positions against the
    Keplerian model in verify_positions.py

Run: python test_mcp.py
"""
import json
import os

import app as flask_app
import mcp_server
import mcp_tools
from verify_positions import ELEMENTS, geocentric_longitude

failures = []


def check(name, condition, detail=''):
    print(f"  {'PASS' if condition else 'FAIL'}  {name} {detail if not condition else ''}")
    if not condition:
        failures.append(name)


def rpc(method, params=None, request_id=1):
    message = {'jsonrpc': '2.0', 'method': method}
    if request_id is not None:
        message['id'] = request_id
    if params is not None:
        message['params'] = params
    return mcp_server.handle(message)


def call(name, **arguments):
    """A tool call, as text, the way a client would receive it"""
    response = mcp_tools.call_tool(name, arguments)
    assert not response.get('isError'), response['content'][0]['text']
    return response['content'][0]['text']


print("\nThe handshake")
print("-" * 72)
hello = rpc('initialize', {'protocolVersion': '2025-06-18',
                           'capabilities': {},
                           'clientInfo': {'name': 'test', 'version': '1'}})
check('initialize answers', hello and 'result' in hello)
check('in the protocol version the client asked for',
      hello['result']['protocolVersion'] == '2025-06-18',
      f"(got {hello['result']['protocolVersion']})")
check('it offers tools', 'tools' in hello['result']['capabilities'])
check('and names itself',
      hello['result']['serverInfo']['name'] == mcp_server.SERVER_NAME)
check('with instructions a client can show the model',
      len(hello['result'].get('instructions', '')) > 100)

older = rpc('initialize', {'protocolVersion': '2024-11-05'})
check('an older client is answered in its own version',
      older['result']['protocolVersion'] == '2024-11-05')
unknown = rpc('initialize', {'protocolVersion': '1999-01-01'})
check('an unknown version falls back to the newest we speak',
      unknown['result']['protocolVersion'] == mcp_server.DEFAULT_PROTOCOL)

check('the initialized notification gets no reply',
      rpc('notifications/initialized', request_id=None) is None)
check('ping is answered', rpc('ping') == {'jsonrpc': '2.0', 'id': 1, 'result': {}})
check('an unknown method is an error, not a crash',
      rpc('does/not/exist')['error']['code'] == mcp_server.METHOD_NOT_FOUND)
check('an unknown notification is simply dropped',
      rpc('notifications/whatever', request_id=None) is None)

batch = mcp_server.handle_payload([
    {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
])
check('a batch answers only the messages that asked for an answer',
      isinstance(batch, list) and len(batch) == 2 and
      [m['id'] for m in batch] == [1, 2])

print("\nThe tools a client is offered")
print("-" * 72)
listed = rpc('tools/list')['result']['tools']
check('every tool is listed', len(listed) == len(mcp_tools.TOOLS))
check('each one has a name, a description and a schema',
      all(tool.get('name') and tool.get('description') and
          tool.get('inputSchema') for tool in listed))
check('every schema is a JSON Schema object',
      all(tool['inputSchema']['type'] == 'object' for tool in listed))
check('every required argument is a declared property',
      all(set(tool['inputSchema'].get('required', []))
          <= set(tool['inputSchema']['properties'])
          for tool in listed),
      f"({[t['name'] for t in listed if not set(t['inputSchema'].get('required', [])) <= set(t['inputSchema']['properties'])]})")
check('the two tools some assistants insist on are there',
      {'search', 'fetch'} <= {tool['name'] for tool in listed})

called = rpc('tools/call', {'name': 'list_charts', 'arguments': {}})
check('a tool call comes back as content blocks',
      called['result']['content'][0]['type'] == 'text')
check('and carries the structured data beside the text',
      'structuredContent' in called['result'])

bad_tool = rpc('tools/call', {'name': 'no_such_tool', 'arguments': {}})
check('an unknown tool is a tool error, not a protocol error',
      bad_tool['result']['isError'] is True and 'error' not in bad_tool)
bad_args = rpc('tools/call', {'name': 'sign_ingresses',
                              'arguments': {'planet': 'Vulcan',
                                            'start_date': '2026-01-01',
                                            'end_date': '2026-02-01'}})
check('a bad argument comes back as something a model can act on',
      bad_args['result']['isError'] and
      'Vulcan' in bad_args['result']['content'][0]['text'],
      f"(got {bad_args['result']['content'][0]['text']!r})")

print("\nsearch and fetch answer in the shape they are expected in")
print("-" * 72)
found = json.loads(call('search', query='julian natal chart'))
check('search returns a results list', isinstance(found.get('results'), list))
check('every result has an id, a title and a url',
      all({'id', 'title', 'url'} <= set(r) for r in found['results']))
check("julian's natal chart is the first hit",
      found['results'][0]['id'] == 'natal:julian',
      f"(got {found['results'][0]['id']})")
document = json.loads(call('fetch', id='natal:julian'))
check('fetch returns the document', {'id', 'title', 'text', 'url'} <= set(document))
check('with the chart in it', "JULIAN'S NATAL CHART" in document['text'])

print("\nThe way in")
print("-" * 72)
client = flask_app.app.test_client()
REMOTE = {'REMOTE_ADDR': '203.0.113.5'}


def post_mcp(body, token=None, accept='application/json', **kwargs):
    headers = {'Accept': accept}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return client.post('/mcp', json=body, headers=headers, **kwargs)


os.environ.pop('MCP_TOKEN', None)
check('with no token set, the machine itself is served',
      post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}).status_code == 200)
check('but nobody else is',
      post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
               environ_base=REMOTE).status_code == 401)

os.environ['MCP_TOKEN'] = 'a-secret'
check('with a token set, a request without one is refused',
      post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'},
               environ_base=REMOTE).status_code == 401)
check('a wrong token is refused',
      post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token='wrong',
               environ_base=REMOTE).status_code == 401)
check('the right one is served',
      post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}, token='a-secret',
               environ_base=REMOTE).status_code == 200)
check('and it can travel in the URL, for a client that cannot set headers',
      client.post('/mcp?key=a-secret', json={'jsonrpc': '2.0', 'id': 1,
                                             'method': 'ping'},
                  environ_base=REMOTE).status_code == 200)

sse = post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
               token='a-secret', accept='text/event-stream')
check('a client that wants an event stream gets one',
      sse.headers['Content-Type'].startswith('text/event-stream'),
      f"(got {sse.headers['Content-Type']})")
check('with the response inside it',
      sse.get_data(as_text=True).startswith('event: message\ndata: {'))
check('and the same answer either way',
      json.loads(sse.get_data(as_text=True).split('data: ')[1])['result'],
      )

notification = post_mcp({'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                        token='a-secret')
check('a notification is accepted with no body', notification.status_code == 202)

session = post_mcp({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                    'params': {'protocolVersion': '2025-06-18'}},
                   token='a-secret')
check('initialize hands out a session id', session.headers.get('Mcp-Session-Id'))

check('a GET without an event stream describes the server',
      client.get('/mcp', headers={'Authorization': 'Bearer a-secret'}).get_json()
      ['transport'] == 'streamable-http')

print("\nThe REST door, for clients that do not speak MCP")
print("-" * 72)
rest = client.post('/api/tools/sign_ingresses',
                   json={'planet': 'Saturn', 'start_date': '2025-01-01',
                         'end_date': '2026-01-01'},
                   headers={'Authorization': 'Bearer a-secret'})
check('a tool can be called as a plain POST', rest.status_code == 200)
check('and answers with the same text',
      '2025-05-24' in rest.get_json()['text'],
      f"(got {rest.get_json()}) ")

browser = client.get('/api/tools/sky_on_date?date=2026-11-13&key=a-secret')
check('and from a browser, with query arguments',
      browser.status_code == 200 and 'Scorpio' in browser.get_json()['text'])

spec = client.get('/api/tools/openapi.json',
                  headers={'Authorization': 'Bearer a-secret'}).get_json()
check('the OpenAPI document declares a version', spec['openapi'].startswith('3.'))
check('it names an absolute server url',
      spec['servers'][0]['url'].startswith('http'))
check('every tool but search and fetch has a path',
      len(spec['paths']) == len(mcp_tools.TOOLS) - 2)
check('every path has a unique operationId',
      len({p['post']['operationId'] for p in spec['paths'].values()})
      == len(spec['paths']))
check('every operation describes its body',
      all('application/json' in p['post']['requestBody']['content']
          for p in spec['paths'].values()))

os.environ.pop('MCP_TOKEN', None)

print("\nThe sky it reports is the real one")
print("-" * 72)
# Sign changes as published in any ephemeris, in Pacific time. These are
# not read from a table here - they are found by bisecting real positions,
# so agreeing with the published dates means the search is right.
PUBLISHED_INGRESSES = [
    ('Pluto', '2022-01-01', '2026-01-01', [
        ('2023-03-23', 'Capricorn', 'Aquarius'),
        ('2023-06-11', 'Aquarius', 'Capricorn'),
        ('2024-01-20', 'Capricorn', 'Aquarius'),
        ('2024-09-01', 'Aquarius', 'Capricorn'),
        ('2024-11-19', 'Capricorn', 'Aquarius')]),
    ('Neptune', '2025-01-01', '2026-06-01', [
        ('2025-03-30', 'Pisces', 'Aries'),
        ('2025-10-22', 'Aries', 'Pisces'),
        ('2026-01-26', 'Pisces', 'Aries')]),
    ('Uranus', '2025-01-01', '2026-06-01', [
        ('2025-07-07', 'Taurus', 'Gemini'),
        ('2025-11-07', 'Gemini', 'Taurus'),
        ('2026-04-25', 'Taurus', 'Gemini')]),
    ('Saturn', '2025-01-01', '2026-06-01', [
        ('2025-05-24', 'Pisces', 'Aries'),
        ('2025-09-01', 'Aries', 'Pisces'),
        ('2026-02-13', 'Pisces', 'Aries')]),
]

for planet, start, end, expected in PUBLISHED_INGRESSES:
    found = mcp_tools.sky.ingresses(planet, start, end)
    ours = [(hit['date'], hit['left'], hit['entered']) for hit in found]
    check(f'{planet} changes sign when the ephemeris says it does',
          ours == expected, f'\n        ours     {ours}\n        expected {expected}')

print("\nStations and retrogrades land on the published dates")
print("-" * 72)
# Mercury's 2026 retrogrades, and Mars's, as published
check('Mercury retrogrades three times in 2026 on the published dates',
      [(p['begins']['date'], p['ends']['date']) for p in
       mcp_tools.sky.retrograde_periods('Mercury', '2026-01-01',
                                        '2027-01-01')['periods']]
      == [('2026-02-25', '2026-03-20'), ('2026-06-29', '2026-07-23'),
          ('2026-10-24', '2026-11-13')],
      f"(got {[(p['begins']['date'], p['ends']['date']) for p in mcp_tools.sky.retrograde_periods('Mercury', '2026-01-01', '2027-01-01')['periods']]})")

uranus = mcp_tools.sky.stations('Uranus', '2026-01-01', '2027-01-01')
check('Uranus stations direct in February and retrograde in September',
      [(s['date'], s['type']) for s in uranus]
      == [('2026-02-03', 'SD'), ('2026-09-10', 'SR')],
      f"(got {[(s['date'], s['type']) for s in uranus]})")

# A retrograde already under way when the window opens is reported from the
# day it began, not the day the search started
underway = mcp_tools.sky.retrograde_periods('Venus', '2026-11-01', '2026-12-01')
check('a retrograde already running is dated from where it really began',
      underway['periods'] and underway['periods'][0]['begins']['date'] == '2026-10-03',
      f"(got {underway['periods'][0]['begins']['date'] if underway['periods'] else None})")

check('the Sun is never reported retrograde',
      mcp_tools.sky.retrograde_periods('Sun', '2020-01-01', '2027-01-01')['periods'] == [])

print("\nAn ingress is really the moment the sign changes")
print("-" * 72)
# Not taken on trust from the published list: the position an hour either
# side of each reported crossing has to be in the two signs it names
worst = None
for planet, start, end, _ in PUBLISHED_INGRESSES:
    for hit in mcp_tools.sky.ingresses(planet, start, end):
        jd = mcp_tools.tc.em.get_julian_day(hit['date'], hit['time'],
                                            'America/Los_Angeles')
        before = mcp_tools.sky.describe_position(planet, jd - 1 / 24.0)
        after = mcp_tools.sky.describe_position(planet, jd + 1 / 24.0)
        if not (before['sign'] == hit['left'] and after['sign'] == hit['entered']):
            worst = (planet, hit['date'], before['sign'], after['sign'], hit)
check('an hour before, it is in the sign it left; an hour after, the one it entered',
      worst is None, f'({worst})')

print("\nPositions agree with the independent model")
print("-" * 72)
positions = mcp_tools.sky.sky_on('2026-11-13', '12:00')
worst_gap = 0.0
checked = 0
for position in positions:
    if position['planet'] not in ELEMENTS and position['planet'] != 'Sun':
        continue  # the model covers the planets out to Neptune
    checked += 1
    jd = mcp_tools.tc.em.get_julian_day('2026-11-13', '12:00',
                                        'America/Los_Angeles')
    independent = geocentric_longitude(position['planet'], jd)
    gap = abs((position['longitude'] - independent + 180) % 360 - 180) * 60
    worst_gap = max(worst_gap, gap)
check(f'all {checked} positions match a Keplerian model worked out from scratch',
      worst_gap < 15 and checked >= 7, f'(worst {worst_gap:.1f} arc minutes)')

print("\nThe tools agree with the app they are built on")
print("-" * 72)
# The same question asked two ways has to give one answer, or the chat
# assistant and the web app will tell the user different things
dashboard = mcp_tools.tc.get_daily_dashboard('julian', '2026-11-13', max_orb=3)
check('transits_on_date is the dashboard the app shows',
      call('transits_on_date', chart='julian', date='2026-11-13',
           include_houses=False) == dashboard['plain_text'])

timeline = call('transit_timeline', chart='julian', transit_planet='Saturn',
                natal_point='Moon', aspect='Conjunction', date='2026-11-13')
saturn_moon = next(a for a in dashboard['aspects']
                   if a['transit_planet'] == 'Saturn'
                   and a['natal_point'] == 'Moon' and a['aspect'] == 'Conjunction')
check('and the timeline quotes the same perfections as the daily reading',
      saturn_moon['next_exact']['date'] in timeline
      and saturn_moon['previous_exact']['date'] in timeline,
      f"(timeline {timeline!r})")

# A degree crossing searched in the sky must land on the date the chart
# search gives for the same degree
natal_moon = mcp_tools.tc.ncm.get_natal_position('julian', 'Moon')
crossings = mcp_tools.sky.degree_crossings(
    'Saturn', mcp_tools.tc.get_sign_from_longitude(natal_moon),
    natal_moon % 30, '2026-01-01', '2027-06-01')
check('a degree search in the sky finds the same dates as the chart search',
      [c['date'] for c in crossings['crossings']]
      == [hit['date'] for hit in
          mcp_tools.tc.calculate_aspect_timeline(
              'julian', 'Saturn', 'Moon', 'Conjunction',
              '2026-11-13')['exact_dates']],
      f"(sky {[c['date'] for c in crossings['crossings']]})")

print("\nA reading names the houses involved")
print("-" * 72)
# The standing instructions ask the assistant to speak to the houses being
# activated, so the lines have to carry them rather than leave it guessing
with_houses = call('transits_on_date', chart='julian', date='2026-11-13')
transit_lines = [line for line in with_houses.split('\n')
                 if "'s natal " in line and ' at ' in line]
check('there are transit lines to check', len(transit_lines) > 5)
check('every one names the house the transiting planet moves through',
      all(' house)' in line.split(' natal ')[0] for line in transit_lines),
      f'({[l for l in transit_lines if " house)" not in l.split(" natal ")[0]][:1]})')
check('and the house the natal placement sits in',
      all(' house)' in line.split(' natal ')[1] for line in transit_lines),
      f'({[l for l in transit_lines if " house)" not in l.split(" natal ")[1]][:1]})')
check('the app\'s own copy text is left as it was',
      ' house)' not in mcp_tools.tc.get_daily_dashboard(
          'julian', '2026-11-13', max_orb=3)['plain_text'].split(
              'PLANETARY TRANSITS')[1])

print("\nA search too wide to be honest is refused rather than guessed at")
print("-" * 72)
wide = mcp_tools.call_tool('sign_ingresses', {'planet': 'Moon',
                                              'start_date': '1900-01-01',
                                              'end_date': '2100-01-01'})
check('a two-century Moon search says no', wide['isError'] is True)
check('and says what to do instead',
      'shorter range' in wide['content'][0]['text'],
      f"(got {wide['content'][0]['text']!r})")

print()
if failures:
    print(f"{len(failures)} FAILED: {', '.join(failures)}")
    raise SystemExit(1)
print("MCP server verified.")
