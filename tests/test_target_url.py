"""The scanner must analyse the exact URL it was given, and say so when it could not.

Covers: deep paths and query strings reach the server unchanged; redirects are
recorded as requested_url vs final_url and flagged; code-repository URLs are
scanned as given with an explanatory note; and the CLI and MCP entry points
report the same thing.
"""

import http.server
import json
import threading

import pytest

from ai_disclosure_scan import cli, mcp_server, report, target, web
from ai_disclosure_scan.models import Status

PAGE = "<html><body><h1>{title}</h1><p>{text}</p>{script}</body></html>"
BOT = '<script src="https://cdn.botpress.cloud/webchat/v2/inject.js"></script>'


def ids(result):
    return {(f.rule_id, f.status) for f in result.findings}


# ---------------------------------------------------------------------------
# A fetcher that records every URL and answers from a table (no network)
# ---------------------------------------------------------------------------


class FakeFetcher(web.Fetcher):
    """Pretends to be the network. routes maps a requested URL to (final URL, html)."""

    def __init__(self, routes):
        super().__init__(respect_robots=False)
        self.routes = routes
        self.requested = []

    def get(self, url, max_bytes):
        self.requested.append(url)
        if url not in self.routes:
            raise web.FetchError("HTTP 404 Not Found")
        final, html = self.routes[url]
        return html.encode(), final, "text/html; charset=utf-8"


def page(title="Page", text="", script=""):
    return PAGE.format(title=title, text=text, script=script)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/owner/repo",
        "https://github.com/eddlev/vm4ai-air-kit",
        "https://example.com/app/chat",
        "https://example.com/app/chat?lang=es&plan=pro",
        "https://example.com/a/b/c/d/e/",
    ],
)
def test_exact_url_is_requested_and_reported(url):
    fetcher = FakeFetcher({url: (url, page())})
    result = web.scan(url, fetcher, check_media=False)
    assert fetcher.requested == [url]  # never the root, never a trimmed path
    assert result.target == result.requested_url == result.final_url == result.analysed_url == url
    assert not any(f.rule_id in {"TGT-001", "TGT-002", "TGT-003"} for f in result.findings)


def test_github_repo_url_gets_an_info_note_and_keeps_its_path():
    url = "https://github.com/owner/repo"
    fetcher = FakeFetcher({url: (url, page(title="owner/repo"))})
    result = web.scan(url, fetcher, check_media=False)
    assert fetcher.requested == [url]
    note = next(f for f in result.findings if f.rule_id == "TGT-004")
    assert note.status is Status.INFO and "owner/repo" in note.detail and note.evidence == url
    assert "https://github.com/" not in {result.final_url, result.analysed_url}


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://www.gitlab.com/group/project/-/tree/main", "group/project"),
        ("https://github.com/owner", ""),
        ("https://github.com/", ""),
        ("https://example.com/owner/repo", ""),
    ],
)
def test_code_repository_detection(url, expected):
    assert target.code_repository(url) == expected


@pytest.mark.parametrize(
    "final, rule, status, reason",
    [
        ("https://example.com/", "TGT-001", Status.REVIEW, "root page"),
        ("https://other.example.org/app/chat", "TGT-001", Status.REVIEW, "different host"),
        ("https://example.com/login?next=/app/chat", "TGT-001", Status.REVIEW, "sign-in"),
        ("https://example.com/es/app/chat", "TGT-002", Status.INFO, "different path"),
    ],
)
def test_redirects_are_recorded_and_flagged(final, rule, status, reason):
    url = "https://example.com/app/chat"
    fetcher = FakeFetcher({url: (final, page(text="You're chatting with our AI assistant.", script=BOT))})
    result = web.scan(url, fetcher, check_media=False)
    assert fetcher.requested == [url]
    assert result.requested_url == url and result.final_url == final
    note = next(f for f in result.findings if f.rule_id == rule)
    assert note.status is status and reason in note.detail
    assert url in note.evidence and final in note.evidence
    if status is Status.REVIEW:
        # every other finding names the page it was actually evaluated on
        for finding in result.findings:
            if not finding.rule_id.startswith("TGT-"):
                assert f"evaluated on {final}" in finding.location


@pytest.mark.parametrize(
    "requested, final",
    [
        ("http://example.com/app", "https://example.com/app"),
        ("https://example.com/app", "https://www.example.com/app/"),
        ("https://example.com/", "https://example.com/"),
        ("https://example.com/app#top", "https://example.com/app"),
    ],
)
def test_harmless_differences_are_not_flagged(requested, final):
    assert target.classify_drift(requested, final) is None


def test_fetch_errors_keep_the_requested_url():
    url = "https://example.com/deep/path?q=1"
    result = web.scan(url, FakeFetcher({}), check_media=False)
    assert result.error and result.requested_url == url
    assert result.to_dict()["requested_url"] == url


# ---------------------------------------------------------------------------
# Real HTTP against a local server that logs every path it is asked for
# ---------------------------------------------------------------------------


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    log = []
    pages = {
        "/owner/repo": page("owner/repo", '<a href="/contact">Contact</a>'),
        "/app/chat": page("App", "Hello", BOT),
        "/": page("ROOT", "You're chatting with our AI assistant.", BOT),
        "/contact": page("Contact"),
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            log.append(self.path)
            path = self.path.split("?")[0]
            if path == "/robots.txt":
                self.send_response(404)
                self.end_headers()
                return
            if path == "/moved":
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            body = pages.get(path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", log
    httpd.shutdown()


def test_server_sees_the_exact_path_and_query(server):
    base, log = server
    result = web.scan(f"{base}/app/chat?x=1&y=2", check_media=False)
    assert log == ["/robots.txt", "/app/chat?x=1&y=2"]
    assert result.final_url == f"{base}/app/chat?x=1&y=2"
    assert ("PAGE-001", Status.REVIEW) in ids(result)


def test_redirect_to_root_is_reported_not_hidden(server):
    base, log = server
    result = web.scan(f"{base}/moved", check_media=False)
    assert log == ["/robots.txt", "/moved", "/"]
    assert result.requested_url == f"{base}/moved" and result.final_url == f"{base}/"
    assert ("TGT-001", Status.REVIEW) in ids(result)
    passed = next(f for f in result.findings if f.rule_id == "PAGE-003")
    assert passed.location == f"evaluated on {base}/"


# ---------------------------------------------------------------------------
# CLI and MCP report the same thing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/owner/repo", "/moved", "/app/chat?x=1"])
def test_cli_and_mcp_agree(server, capsys, path):
    base, _ = server
    url = base + path
    code = cli.main(["page", url, "--format", "json", "--no-media", "--fail-on", "never"])
    assert code == 0
    from_cli = json.loads(capsys.readouterr().out)
    reply = mcp_server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": "scan_page", "arguments": {"urls": [url], "check_media": False}}}
    )  # fmt: skip
    from_mcp = json.loads(reply["result"]["content"][0]["text"])
    for data in (from_cli, from_mcp):
        assert data["scope"] == report.SCOPE
        assert data["results"][0]["requested_url"] == url
    keys = ("requested_url", "final_url", "analysed_url")
    assert [from_cli["results"][0][k] for k in keys] == [from_mcp["results"][0][k] for k in keys]
    rule_ids = lambda d: sorted(f["rule_id"] for f in d["results"][0]["findings"])  # noqa: E731
    assert rule_ids(from_cli) == rule_ids(from_mcp)


def test_scope_line_in_every_format(capsys, tmp_path):
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / "examples" / "sites" / "northwind-good"
    for fmt in ("text", "md", "html", "json"):
        cli.main(["page", str(example), "--format", fmt, "--no-media"])
        out = capsys.readouterr().out
        assert "Not legal advice, and not a conformity assessment or certification." in out, fmt
        assert "requested: " in out or '"requested_url"' in out, fmt


# ---------------------------------------------------------------------------
# Browser mode over HTTP
# ---------------------------------------------------------------------------


def _browser_ok():
    from ai_disclosure_scan import browser

    if not browser.available()[0]:
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser._launch(pw).close()
        return True
    except Exception:  # noqa: BLE001
        return False


needs_browser = pytest.mark.skipif(not _browser_ok(), reason="Playwright with a Chromium browser is not available")


@needs_browser
def test_browser_mode_keeps_deep_path_and_never_follows_contact(server):
    base, log = server
    result = web.scan(f"{base}/owner/repo", check_media=False, use_browser=True, browser_timeout=15, follow_contact=True)
    assert "/contact" not in log and "/" not in log  # a deep URL is never swapped for another page
    assert result.requested_url == result.final_url == result.analysed_url == f"{base}/owner/repo"
    assert not any(f.rule_id.startswith("TGT-") for f in result.findings)


@needs_browser
def test_browser_mode_reports_redirect_to_root(server):
    base, _ = server
    result = web.scan(f"{base}/moved", check_media=False, use_browser=True, browser_timeout=15)
    assert result.requested_url == f"{base}/moved" and result.final_url == f"{base}/"
    assert ("TGT-001", Status.REVIEW) in ids(result)
