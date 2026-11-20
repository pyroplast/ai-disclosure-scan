"""MCP server: lets an AI agent call the scans as tools.

Speaks the Model Context Protocol over stdio (newline-delimited JSON-RPC 2.0),
written against the standard library so the package stays dependency-free.

    ai-disclosure-scan mcp

Tools
    scan_page        scan a web page by URL (optionally in a real browser)
    scan_transcript  scan conversation text the agent already has
    scan_files       scan transcript or media files on disk
    list_rules       the rule catalogue with the legal basis of each check
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import __version__, media, report, rules, transcript, web
from .models import Report, TargetResult

SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = (
    "Technical readiness checks for the transparency duties in Article 50 of the EU AI Act. "
    "Every finding carries a status (gap, review, pass, info), the rule it comes from, evidence, "
    "and the legal basis: the paragraph and sentence of Article 50 with a link. "
    "When you report results, say that this is a technical check and not legal advice, quote the "
    "pinpoint for each gap, and do not describe 'review' findings as violations. "
    "Page results carry requested_url, final_url and analysed_url: report findings for the page they were "
    "evaluated on, and pass on any TGT-* note, which means the analysed page differs from the one requested. "
    "Every response includes a 'scope' field; relay it."
)

_URL = {"type": "string", "description": "Full URL including https://"}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "scan_page",
        "title": "Scan a web page for AI disclosure",
        "description": (
            "Scan web pages for chat or voice widgets, a visible notice that the chat is an AI, hidden AI "
            "wording, and AI-made media without a visible label. Set browser=true to render the page in a "
            "headless browser and open the chat widget, which turns guesses into observations (needs "
            "Playwright on the machine running this server). Returns a JSON report."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": _URL, "minItems": 1, "maxItems": 20},
                "browser": {"type": "boolean", "default": False, "description": "Open the widget in a real browser"},
                "check_media": {"type": "boolean", "default": True},
                "respect_robots": {"type": "boolean", "default": True},
            },
            "required": ["urls"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "scan_transcript",
        "title": "Scan a chatbot conversation",
        "description": (
            "Check whether an assistant tells people it is an AI, and in its first message. Flags late "
            "disclosure, claims to be human, dodged 'are you a bot?' questions and generic labels. Accepts "
            "JSON (a list of {role, content} messages, or an object with 'messages'), JSONL, or a plain "
            "chat log with 'User:' / 'Assistant:' lines. Eight languages."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The conversation(s)"},
                "name": {"type": "string", "description": "Label for the report", "default": "transcript"},
                "ui_notice": {
                    "type": "boolean",
                    "default": False,
                    "description": "The chat UI shows a visible AI notice before the first reply",
                },
            },
            "required": ["text"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "scan_files",
        "title": "Scan transcript or media files",
        "description": (
            "Scan files or folders on the machine running this server. kind='transcript' for exported "
            "conversations, kind='media' for images, audio and video (reads C2PA and IPTC AI marking)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "kind": {"type": "string", "enum": ["transcript", "media"]},
            },
            "required": ["paths", "kind"],
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
    {
        "name": "list_rules",
        "title": "List the checks and their legal basis",
        "description": "Every rule with its Article 50 paragraph, duty holder, sources with pinpoints and links, and the scanner's own reading.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    },
]


class ToolError(Exception):
    pass


def _report(results: list[TargetResult]) -> str:
    rep = Report(__version__, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), results)
    return report.to_json(rep)


def _scan_page(args: dict[str, Any]) -> str:
    urls = args.get("urls") or ([args["url"]] if args.get("url") else [])
    if not urls or not all(isinstance(u, str) and web.is_url(u) for u in urls):
        raise ToolError("urls must be a non-empty list of http(s) URLs")
    if len(urls) > 20:
        raise ToolError("at most 20 URLs per call")
    fetcher = web.Fetcher(respect_robots=bool(args.get("respect_robots", True)))
    use_browser = bool(args.get("browser", False))
    if use_browser:
        from . import browser

        ok, hint = browser.available()
        if not ok:
            raise ToolError(hint)
    results = [
        web.scan(u, fetcher, check_media=bool(args.get("check_media", True)), use_browser=use_browser) for u in urls
    ]
    return _report(results)


def _scan_transcript(args: dict[str, Any]) -> str:
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ToolError("text must be a non-empty string")
    return _report(
        transcript.scan_text(text, name=str(args.get("name") or "transcript"), ui_notice=bool(args.get("ui_notice")))
    )


def _scan_files(args: dict[str, Any]) -> str:
    paths = args.get("paths") or []
    kind = args.get("kind")
    if kind not in ("transcript", "media"):
        raise ToolError("kind must be 'transcript' or 'media'")
    results: list[TargetResult] = []
    for raw in paths:
        path = Path(str(raw)).expanduser()
        if not path.exists():
            results.append(TargetResult(str(path), kind, error="no such file or folder"))
        elif kind == "transcript":
            results.extend(transcript.scan_path(path))
        else:
            results.extend(media.scan_path(path))
    return _report(results)


def _list_rules(_: dict[str, Any]) -> str:
    return json.dumps(
        {"scope": report.SCOPE, "rules": [r.to_dict() for r in rules.all_rules()]}, indent=2, ensure_ascii=False
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "scan_page": _scan_page,
    "scan_transcript": _scan_transcript,
    "scan_files": _scan_files,
    "list_rules": _list_rules,
}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    """Answer one JSON-RPC message. Returns None for notifications."""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    is_request = "id" in message

    def ok(result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def err(code: int, text: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": text}}

    if not is_request:
        return None  # notifications/initialized, notifications/cancelled, ...
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return ok(
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ai-disclosure-scan", "title": "AI disclosure scan", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        )
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return err(-32602, f"unknown tool: {name}")
        try:
            text = handler(params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except ToolError as exc:
            return ok({"content": [{"type": "text", "text": str(exc)}], "isError": True})
        except Exception as exc:  # noqa: BLE001 - a tool failure must not kill the server
            traceback.print_exc(file=sys.stderr)
            return ok({"content": [{"type": "text", "text": f"internal error: {exc}"}], "isError": True})
    return err(-32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply: dict[str, Any] | None = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            batch = message if isinstance(message, list) else [message]
            replies = [r for r in (handle(m) for m in batch if isinstance(m, dict)) if r is not None]
            reply = None if not replies else (replies if isinstance(message, list) else replies[0])
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()
    return 0
