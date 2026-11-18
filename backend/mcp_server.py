"""
MCP for the transit engine.

This is the protocol layer: JSON-RPC in, JSON-RPC out, over whichever
transport is carrying it. The tools themselves live in mcp_tools.py.

Two ways to run it:

  stdio  - python mcp_server.py
           For a desktop client that launches the server itself (Claude
           Desktop, Claude Code, Cursor). Nothing is exposed to a network.

  HTTP   - the Flask app serves /mcp (see mcp_http.py)
           For a hosted client that connects to a URL (ChatGPT's custom
           connectors, Claude's remote connectors).

Both read the same tool registry, so an answer does not depend on how the
question arrived.
"""
import json
import sys
import uuid

import mcp_tools

SERVER_NAME = 'astrology-transits'
SERVER_VERSION = '1.0.0'

# Versions of the protocol this server knows how to speak. A client asking
# for one of these is answered in its own version; anything else is
# answered in the newest one we know, which the spec allows.
SUPPORTED_PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05']
DEFAULT_PROTOCOL = SUPPORTED_PROTOCOLS[0]

INSTRUCTIONS = """
Real astronomical positions from the Swiss Ephemeris, for the sky itself and
for a set of stored natal charts.

Dates and times are Pacific by default, and every answer says which timezone
it is in. Pass `timezone` for anything else.

Exactness here means the moment an aspect reaches 0°00', never the moment it
stops applying: a planet that stations short of an aspect is reported as
never having perfected it, and a retrograde that crosses the same point three
times gets three dates.

For anything with a date, a planet or a range in it, call the tool that fits
it. Do not work positions out from memory - ask for them, and quote the
degrees, signs and dates as they come back rather than rounding them into
"early Libra" or "later this month".

Reading a chart usually takes more than one call:

  - sky_on_date for where the planets are now, which is the context
    everything else sits in
  - transits_on_date for what is touching a chart, with the house each
    transiting planet is moving through and the house each natal placement
    sits in
  - transit_timeline when the passes matter: it lists every perfection in
    the window, so it is what tells you whether a transit has made one pass
    of three, or is on its last
  - retrograde_periods and stations for what is retrograde now, and when it
    turns

Retrograde is never a detail to drop. Say when a transiting planet is
retrograde, and say when a transit perfects again after a station rather
than letting it read as finished.
""".strip()

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


def error(request_id, code, message):
    return {'jsonrpc': '2.0', 'id': request_id,
            'error': {'code': code, 'message': message}}


def result(request_id, payload):
    return {'jsonrpc': '2.0', 'id': request_id, 'result': payload}


def handle(message):
    """
    One JSON-RPC message in, one response out.

    Returns None for a notification, which by the spec gets no reply.
    """
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
        return error(None, INVALID_REQUEST, 'Expected a JSON-RPC 2.0 message')

    method = message.get('method')
    request_id = message.get('id')
    params = message.get('params') or {}
    is_notification = 'id' not in message

    if method == 'initialize':
        asked_for = params.get('protocolVersion')
        return result(request_id, {
            'protocolVersion': (asked_for if asked_for in SUPPORTED_PROTOCOLS
                                else DEFAULT_PROTOCOL),
            'capabilities': {'tools': {'listChanged': False}},
            'serverInfo': {'name': SERVER_NAME, 'version': SERVER_VERSION},
            'instructions': INSTRUCTIONS
        })

    if method in ('notifications/initialized', 'initialized',
                  'notifications/cancelled'):
        return None

    if method == 'ping':
        return result(request_id, {})

    if method == 'tools/list':
        return result(request_id, {'tools': mcp_tools.list_tools()})

    if method == 'tools/call':
        name = params.get('name')
        arguments = params.get('arguments') or {}
        return result(request_id, mcp_tools.call_tool(name, arguments))

    # Clients commonly ask for these on connecting; an empty list is a
    # truer answer than "no such method"
    if method == 'resources/list':
        return result(request_id, {'resources': []})
    if method == 'resources/templates/list':
        return result(request_id, {'resourceTemplates': []})
    if method == 'prompts/list':
        return result(request_id, {'prompts': []})

    if is_notification:
        return None

    return error(request_id, METHOD_NOT_FOUND, f"Unknown method '{method}'")


def handle_payload(payload):
    """
    Handle a parsed request body, which may be a batch.

    Returns the response to send, or None when there is nothing to send
    (a body of nothing but notifications).
    """
    if isinstance(payload, list):
        if not payload:
            return error(None, INVALID_REQUEST, 'Empty batch')
        responses = [response for response in (handle(m) for m in payload)
                     if response is not None]
        return responses or None
    return handle(payload)


def new_session_id():
    return uuid.uuid4().hex


def serve_stdio():
    """Read JSON-RPC from stdin, write responses to stdout, a line at a time"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            response = error(None, PARSE_ERROR, 'Invalid JSON')
        else:
            try:
                response = handle_payload(payload)
            except Exception as failure:  # a crash must not kill the server
                request_id = payload.get('id') if isinstance(payload, dict) else None
                response = error(request_id, INTERNAL_ERROR, str(failure))

        if response is not None:
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()


if __name__ == '__main__':
    serve_stdio()
