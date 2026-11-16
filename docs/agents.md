# Connect the scanner to your AI agent

`ai-disclosure-scan mcp` runs the scanner as an [MCP](https://modelcontextprotocol.io) server. Any agent that speaks MCP (Claude Desktop, Claude Code, Cursor, and others) can then call the scans as tools. Ask it in plain words:

> Check whether the chat on northwind.example tells visitors it's an AI. Open the widget.

> Here's a conversation export from our support bot. Does it disclose on time?

> Scan the images in ~/site/assets for AI marking.

The server runs on your machine and fetches pages from there, so the agent can scan any site your machine can reach.

## Tools

| Tool | What it does |
|---|---|
| `scan_page` | Scan up to 20 URLs. `browser: true` opens the chat widget in a headless browser |
| `scan_transcript` | Scan conversation text the agent already has (JSON, JSONL or a plain chat log) |
| `scan_files` | Scan transcript or media files and folders on disk |
| `list_rules` | Every check with its Article 50 pinpoint, sources and links |

Every tool returns the JSON report: status, evidence, fix, and the legal basis of each finding. The server tells the agent to present results as a technical check, cite the pinpoint for each gap, and not call `review` findings violations.

## Set it up

You need Python 3.9 or newer. The commands below use [uv](https://docs.astral.sh/uv/), which installs nothing permanently. If you prefer, `pipx install git+https://github.com/pyroplast/ai-disclosure-scan` and use `ai-disclosure-scan mcp` as the command instead.

### Claude Code

```bash
claude mcp add ai-disclosure-scan -- uvx --from git+https://github.com/pyroplast/ai-disclosure-scan ai-disclosure-scan mcp
```

### Claude Desktop

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "ai-disclosure-scan": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/pyroplast/ai-disclosure-scan", "ai-disclosure-scan", "mcp"]
    }
  }
}
```

Restart Claude Desktop. If it cannot find `uvx`, put the full path from `which uvx` in `command`.

### Cursor

Add the same `mcpServers` block to `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).

### Any other MCP client

Command `uvx`, arguments `--from git+https://github.com/pyroplast/ai-disclosure-scan ai-disclosure-scan mcp`, transport stdio.

## Turn on browser mode for the agent

`scan_page` with `browser: true` needs Playwright and a Chromium browser where the server runs. With uv:

```json
"args": ["--from", "ai-disclosure-scan[browser] @ git+https://github.com/pyroplast/ai-disclosure-scan", "ai-disclosure-scan", "mcp"]
```

then, once:

```bash
uvx --from playwright playwright install chromium
```

If Google Chrome is installed, the scanner uses it when Playwright's own Chromium is missing.

## Be a good neighbour

The scanner identifies itself in its user agent and respects `robots.txt` by default (`respect_robots: false` overrides it). It sends one request for a page, up to 12 for its media, and in browser mode loads the page once like a visitor would. Results are signals about what a visitor sees, not legal findings: do not publish claims about a named company on the strength of a `review`.
