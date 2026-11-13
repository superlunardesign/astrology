"""
The transit engine over HTTP, two ways.

  /mcp               MCP over Streamable HTTP, for a client that speaks MCP
                     (ChatGPT custom connectors, Claude remote connectors).

  /api/tools/<name>  The same tools as plain JSON POSTs, described by an
                     OpenAPI document at /api/tools/openapi.json. For a
                     Custom GPT Action, or anything else that would rather
                     call a REST endpoint than learn a protocol.

Both run the tools in mcp_tools.py, so the two front doors give the same
answers.

Access: set MCP_TOKEN in the environment and send it as `Authorization:
Bearer <token>`, as `X-API-Key: <token>`, or as `?key=<token>` on the URL
for a client that cannot set headers. Without MCP_TOKEN set, only requests
from the machine itself are served - these charts are somebody's birth data
and the endpoint is otherwise open to anyone who finds the URL.
"""
import json
import os

from flask import Blueprint, Response, jsonify, request

import mcp_server
import mcp_tools

mcp_blueprint = Blueprint('mcp', __name__)

LOCAL_ADDRESSES = ('127.0.0.1', '::1', 'localhost')

NO_TOKEN_MESSAGE = (
    'This server has no MCP_TOKEN set, so it only answers requests from the '
    'machine it runs on. Set MCP_TOKEN in the environment to use it remotely, '
    'and send that token as a Bearer token, an X-API-Key header, or ?key= on '
    'the URL.'
)


def presented_token():
    header = request.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        return header[7:].strip()
    return (request.headers.get('X-API-Key')
            or request.args.get('key')
            or '')


def authorized():
    """
    Is this request allowed through?

    Returns (True, None) or (False, reason).
    """
    expected = os.environ.get('MCP_TOKEN', '').strip()

    if not expected:
        if request.remote_addr in LOCAL_ADDRESSES:
            return True, None
        return False, NO_TOKEN_MESSAGE

    presented = presented_token()
    if not presented:
        return False, 'Missing token. Send Authorization: Bearer <token>.'

    # Length-independent comparison, so a wrong token says nothing about
    # how wrong it is
    import hmac
    if not hmac.compare_digest(presented, expected):
        return False, 'That token is not the one this server expects.'

    return True, None


# ----------------------------------------------------------------------
# MCP over Streamable HTTP
# ----------------------------------------------------------------------

def as_sse(payload):
    """One JSON-RPC response as a server-sent event"""
    return Response(f'event: message\ndata: {json.dumps(payload)}\n\n',
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})


@mcp_blueprint.route('/mcp', methods=['POST'])
def mcp_post():
    allowed, reason = authorized()
    if not allowed:
        return jsonify(mcp_server.error(None, -32001, reason)), 401

    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify(mcp_server.error(
            None, mcp_server.PARSE_ERROR, 'Invalid JSON')), 400

    try:
        response = mcp_server.handle_payload(payload)
    except Exception as failure:
        request_id = payload.get('id') if isinstance(payload, dict) else None
        response = mcp_server.error(
            request_id, mcp_server.INTERNAL_ERROR, str(failure))

    # A body of nothing but notifications gets no content back
    if response is None:
        return '', 202

    headers = {}
    # A session id is handed out on initialize for clients that track one.
    # This server keeps no state between calls, so it accepts any id it is
    # given afterwards, including none.
    if isinstance(payload, dict) and payload.get('method') == 'initialize':
        headers['Mcp-Session-Id'] = (request.headers.get('Mcp-Session-Id')
                                     or mcp_server.new_session_id())

    accepts = request.headers.get('Accept', '')
    if 'text/event-stream' in accepts:
        stream = as_sse(response)
        stream.headers.extend(headers)
        return stream

    reply = jsonify(response)
    reply.headers.extend(headers)
    return reply


@mcp_blueprint.route('/mcp', methods=['GET'])
def mcp_get():
    """
    The stream a Streamable HTTP client may open for server-sent messages.

    This server only ever answers requests, so the stream carries nothing.
    It is here because a client that opens one and gets a 404 may decide
    the server is not an MCP server at all.
    """
    allowed, reason = authorized()
    if not allowed:
        return jsonify({'error': reason}), 401

    if 'text/event-stream' not in request.headers.get('Accept', ''):
        return jsonify({
            'server': mcp_server.SERVER_NAME,
            'version': mcp_server.SERVER_VERSION,
            'transport': 'streamable-http',
            'tools': len(mcp_tools.TOOLS),
            'post_to': request.base_url
        })

    def nothing():
        # An open stream with a comment, which keeps proxies from closing it
        yield ': connected\n\n'

    return Response(nothing(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})


@mcp_blueprint.route('/mcp', methods=['DELETE'])
def mcp_delete():
    """End a session. Nothing is stored, so there is nothing to end."""
    return '', 204


# ----------------------------------------------------------------------
# The same tools as plain REST, for clients that do not speak MCP
# ----------------------------------------------------------------------

@mcp_blueprint.route('/api/tools', methods=['GET'])
def list_tool_endpoints():
    allowed, reason = authorized()
    if not allowed:
        return jsonify({'error': reason}), 401

    return jsonify({'tools': mcp_tools.list_tools()})


@mcp_blueprint.route('/api/tools/<name>', methods=['POST', 'GET'])
def call_tool_endpoint(name):
    allowed, reason = authorized()
    if not allowed:
        return jsonify({'error': reason}), 401

    if request.method == 'GET':
        # Query string arguments, so a tool can be tried from a browser.
        # Everything arrives as text, so the obvious types are read back.
        arguments = {key: read_value(value)
                     for key, value in request.args.items() if key != 'key'}
    else:
        arguments = request.get_json(silent=True) or {}

    result = mcp_tools.call_tool(name, arguments)
    text = '\n'.join(block['text'] for block in result['content']
                     if block['type'] == 'text')

    if result.get('isError'):
        return jsonify({'error': text}), 400

    structured = result.get('structuredContent') or {}
    return jsonify({'text': text, **structured})


def read_value(value):
    """Read a query string value as the type it looks like"""
    if value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


@mcp_blueprint.route('/api/tools/openapi.json', methods=['GET'])
def openapi_document():
    """
    An OpenAPI description of the tools, for a Custom GPT Action or any
    other client that works from a schema rather than from MCP.
    """
    base = request.url_root.rstrip('/')
    # Behind a proxy that terminates TLS, the scheme seen here is http
    forwarded = request.headers.get('X-Forwarded-Proto')
    if forwarded:
        base = forwarded.split(',')[0].strip() + base[base.index('://'):]

    paths = {}
    for tool in mcp_tools.TOOLS.values():
        if tool['name'] in ('search', 'fetch'):
            continue  # those two exist for MCP clients that require them
        paths[f"/api/tools/{tool['name']}"] = {
            'post': {
                'operationId': tool['name'],
                'summary': tool['description'].split('\n')[0],
                'description': tool['description'],
                'requestBody': {
                    'required': bool(tool['inputSchema'].get('required')),
                    'content': {'application/json': {
                        'schema': tool['inputSchema']}}
                },
                'responses': {
                    '200': {
                        'description': 'The reading',
                        'content': {'application/json': {'schema': {
                            'type': 'object',
                            'properties': {
                                'text': {'type': 'string',
                                         'description': 'The answer, written out'}
                            }
                        }}}
                    }
                }
            }
        }

    return jsonify({
        'openapi': '3.1.0',
        'info': {
            'title': 'Astrology transits',
            'description': mcp_server.INSTRUCTIONS,
            'version': mcp_server.SERVER_VERSION
        },
        'servers': [{'url': base}],
        'paths': paths,
        'components': {
            'securitySchemes': {
                'bearer': {'type': 'http', 'scheme': 'bearer'}
            }
        },
        'security': [{'bearer': []}]
    })
