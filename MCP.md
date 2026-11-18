# Connecting this to a chat assistant

The transit engine is also available as a set of tools a chat assistant can
call, so you can ask ChatGPT or Claude a question in plain language and have
it answered from the real ephemeris instead of from the model's memory.

There are two front doors. They run the same tools and give the same answers:

| Door | URL | For |
|---|---|---|
| MCP | `https://<your-app>/mcp` | ChatGPT custom connectors, Claude connectors, Claude Desktop, Cursor |
| REST + OpenAPI | `https://<your-app>/api/tools/openapi.json` | A Custom GPT Action, or anything that calls a plain API |

Use whichever your assistant supports. The REST door needs no MCP support
anywhere and works on any ChatGPT plan that can build a Custom GPT.

---

## The tools

**The sky on its own** — no chart needed, any date past or future.

- `sky_on_date` — every planet's sign, degree and direction at a moment
- `planet_track` — where a planet travelled between two dates, the ground it
  covered and the signs it passed through
- `sign_ingresses` — every sign change in a span, retrograde re-entries included
- `time_in_sign` — when a planet was in a sign, as dated stretches
- `retrograde_periods` — every retrograde stretch, with the degrees it covered
- `stations` — every turn-around and the degree it happened at
- `degree_crossings` — when a planet reached an exact degree, or an exact
  aspect to one

**The stored charts**

- `list_charts` — what charts exist
- `natal_chart` — placements, cusps, house rulers
- `transits_on_date` — the app's daily reading
- `transit_passes` — one transit searched across years or a whole life:
  every pass it makes, grouped into the approach it belongs to, each marked
  direct or retrograde, with the age it falls at. This is the one for "when
  does Saturn next conjoin my Moon", "how many passes does this make", "has
  this ever happened to me"
- `transit_timeline` — one transit from entering orb to leaving it, around a
  date it is actually near
- `scan_transits` — everything perfecting between two dates, narrowable to
  particular planets, aspects or natal placements
- `transit_journal` — the day-by-day writeup, up to 30 days
- `progressions` — secondary progressions and solar arc

**For assistants that require them**

- `search` and `fetch` — the pair some clients insist on before they will
  connect. The tools above answer better.

Dates and times are Pacific unless you pass `timezone`, and every answer says
which zone it is in.

---

## Setting a token first

These charts are somebody's birth data, and a URL on the open internet is
findable. So:

- With `MCP_TOKEN` set in the environment, a request must carry it.
- Without `MCP_TOKEN` set, only the machine the server runs on is served.
  Remote requests get a 401 explaining this.

On Render: **Environment → Add Environment Variable**, `MCP_TOKEN`, a long
random string. Anything from a password manager is fine.

A request can carry it three ways, whichever your client can manage:

```
Authorization: Bearer <token>
X-API-Key: <token>
https://<your-app>/mcp?key=<token>      # for a client with no header field
```

---

## ChatGPT

### As a connector (MCP)

1. Settings → Connectors → Advanced → turn on **Developer mode**.
2. Settings → Connectors → **Create**.
3. URL: `https://<your-app>/mcp?key=<your token>`
4. Authentication: **No authentication** — the token is in the URL.
   If the form offers a custom header instead, use
   `Authorization: Bearer <token>` and leave the URL clean.
5. In a chat, turn the connector on from the **+** menu.

Developer mode is a beta feature and ChatGPT moves it around; if you cannot
find it, use the Custom GPT route below, which needs none of it.

### As a Custom GPT Action (no MCP, no developer mode)

1. ChatGPT → **Explore GPTs** → **Create** → **Configure** → **Create new action**.
2. **Import from URL**: `https://<your-app>/api/tools/openapi.json`
3. Authentication: **API Key**, type **Bearer**, and paste your token.
4. Save. Ask it questions.

The OpenAPI document is generated from the same tool list, so it stays in
step with the server by itself.

---

## Claude

### As a remote connector

Settings → Connectors → **Add custom connector**, URL
`https://<your-app>/mcp?key=<your token>`.

### Running locally, no hosting involved

Claude Desktop → Settings → Developer → Edit Config, and add:

```json
{
  "mcpServers": {
    "astrology": {
      "command": "python",
      "args": ["/full/path/to/astrology/backend/mcp_server.py"]
    }
  }
}
```

Nothing is exposed to a network this way, so no token is needed. Use the
Python that has this project's requirements installed — the full path to a
virtualenv's `python` if you made one.

---

## Telling the assistant how you want it to read

The server sends a client its own instructions on connecting - call the
tools, don't recall positions, quote exact degrees, never drop a retrograde.
That covers the facts. How you want a reading *written* is a separate thing,
and belongs in the assistant rather than the server.

Paste this into a Custom GPT's instructions, or a ChatGPT Project's custom
instructions, and every chat in it starts there:

> When asked about astrology, use the current global position of the planets,
> transits to the charts mentioned, what houses and signs are being activated
> or are involved, and be cognizant of if there are retrograde passes,
> currently planets in retrograde, and how many passes may have already been
> made by a specific transit or will eventually be made. Consider the
> difference in retrograde versus direct and how those energies are different
> if it is worth noting. Don't over-assume everything is relationship related,
> but don't hide from actual observations that seem connected.
>
> Even though we already know you cannot guarantee outcomes or predict the
> future, we want to treat this as predictive and weigh the astrology more
> heavily than what real life context suggests. This is because humans are not
> perfect. They may say one thing and later do another. Take an action that
> means to be rigid in the moment and later go against it, etc. Therefore,
> weigh the astrology more heavily and only use real life context as just
> that - context.
>
> I am Christina. Julian is my partner. The "davison" chart is our
> relationship chart. If I say "me" or "my chart" use christina; "us" or "our
> chart" means davison. Ask which chart I mean if it is genuinely ambiguous.

The pass counting in the first paragraph is `transit_timeline`'s job - it
returns every perfection in a transit's window, so "second of three passes"
is something the assistant can state rather than estimate. `transits_on_date`
names the houses on both sides of every aspect, so those do not have to be
worked out either.

## Questions it answers well

> Where was Mars when I was born, and when did it next come back to that degree?

> When did Pluto enter Aquarius, and how many times did it cross back?

> Saturn's been in Aries since May 2025 — when does it leave for good?

> What's perfecting for Julian between now and the end of February?

> When does Mercury go retrograde next and what degrees does it cover?

> When does Saturn next conjoin my Moon, and how many passes does it make?

> Has transiting Pluto ever squared my Sun? How old was I?

> Everything the outer planets do to my Ascendant between now and 2050.

Anything with a date, a planet or a range in it should be sent to a tool. The
server's instructions tell the assistant as much, but if you see it answering
from memory, telling it to "use the astrology tools" fixes it.

---

## Checking it

```bash
python backend/test_mcp.py
```

61 checks: the protocol handshake, both content types, the token rules, the
OpenAPI document, and the answers themselves — sign changes, stations and
retrogrades against dates published independently of this code, positions
against a Keplerian model worked out from scratch, and the tool output against
what the web app shows for the same question.

A quick look by hand, with the server running locally:

```bash
curl "http://127.0.0.1:5000/api/tools/sign_ingresses?planet=Pluto&start_date=2022-01-01&end_date=2026-01-01"
```
