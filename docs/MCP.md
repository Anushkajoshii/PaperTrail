# PaperTrail for AI assistants (MCP server)

PaperTrail includes a [Model Context Protocol](https://modelcontextprotocol.io) server, so an AI
assistant or IDE that supports MCP can use PaperTrail as a tool. For example: *"Fact-check this
Instagram caption"* or *"Did this creator's stock calls come true?"*

It calls the PaperTrail API (the live deployment by default), so it needs no AWS or AI keys of
its own.

## Tools

| Tool | What it does | Changes anything? |
|---|---|---|
| `check_content(text, creator_handle?, wait_seconds=90)` | Fact-checks a post, caption or transcript in English, Hindi or Hinglish, and waits for the verdicts | Creates a check |
| `get_check(check_id)` | Progress or result of a check | No |
| `creator_profile(handle)` | Track record of checked claims, stock calls and red-flag timeline | No |
| `compare_creators(handles)` | 2–3 creators side by side, not a recommendation | No |
| `claim_ledger()` | Recent stock calls and whether they came true | No |
| `sebi_rulebook()` | The red-flag checks and the official SEBI sources behind them | No |

Every result links back to the full page and the downloadable report, and carries PaperTrail's
notices:
- Verdicts are about claims, not people.
- It is not financial advice.
- SEBI registration does not mean endorsement.

The server also gives the assistant instructions to keep that wording when it relays results.

## Set it up

You need [uv](https://docs.astral.sh/uv/) and a copy of this repository.

```bash
git clone https://github.com/Anushkajoshii/PaperTrail.git
cd PaperTrail && uv sync --extra mcp
```

Then add a server entry to your assistant's MCP configuration. Most clients use this JSON shape,
with the path changed to where you cloned the repository:

```json
{
  "mcpServers": {
    "papertrail": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/PaperTrail", "--extra", "mcp", "papertrail-mcp"]
    }
  }
}
```

To use a local API instead of the live one (for example while developing, after `make dev`),
add `"env": {"PAPERTRAIL_API_URL": "http://localhost:8000"}` to the entry.

## Try it without an assistant

```bash
uv run --extra mcp python -c "
import asyncio, json
from papertrail.mcp_server import build_server
r = asyncio.run(build_server().call_tool('sebi_rulebook', {}))
print(json.loads(r.content[0].text)['rules'][0]['title'])"
```

## Design notes

- The server is a thin client over the public API. It holds no secrets and stores nothing.
- Read-only tools are marked `read_only_hint`. Only `check_content` creates anything: one check,
  which is rate-limited by the API like any other.
- Errors such as an unknown check or a creator with no checks come back as clear tool errors, not
  crashes.
- The code is in `papertrail/mcp_server.py` and the tests in `tests/test_mcp_server.py`. The
  tests use a fake API, so they need no network.
