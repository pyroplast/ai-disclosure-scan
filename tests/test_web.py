import functools
import http.server
import threading
from pathlib import Path

import pytest

from ai_disclosure_scan import web
from ai_disclosure_scan.models import Status

SITES = Path(__file__).resolve().parent.parent / "examples" / "sites"


def ids(result):
    return {(f.rule_id, f.status) for f in result.findings}


def scan_html(tmp_path, html, **kwargs):
    file = tmp_path / "index.html"
    file.write_text(html, encoding="utf-8")
    return web.scan(str(file), **kwargs)


BOT = '<script src="https://cdn.botpress.cloud/webchat/v2/inject.js"></script>'


def test_example_bad_site():
    result = web.scan(str(SITES / "northwind-bad"))
    assert ids(result) == {("PAGE-001", Status.REVIEW), ("LBL-001", Status.REVIEW)}
    assert result.facts["widgets"] == [{"name": "Botpress", "kind": "ai"}]
    assert result.facts["media_inspected"] == 2
    assert len(result.facts["ai_media"]) == 1


def test_example_good_site():
    result = web.scan(str(SITES / "northwind-good" / "index.html"))
    assert ids(result) == {("PAGE-003", Status.PASS), ("LBL-002", Status.PASS)}


def test_example_hidden_site():
    result = web.scan(str(SITES / "northwind-hidden"))
    assert ids(result) == {("PAGE-004", Status.REVIEW), ("LBL-003", Status.REVIEW)}


def test_no_widget(tmp_path):
    result = scan_html(tmp_path, "<html><body><p>Hello</p></body></html>")
    assert ids(result) == {("PAGE-005", Status.INFO)}


def test_marketing_mention_is_review(tmp_path):
    result = scan_html(tmp_path, f"<body><p>We use AI to plan delivery routes.</p>{BOT}</body>")
    assert ids(result) == {("PAGE-002", Status.REVIEW)}


def test_notice_inside_widget_configuration(tmp_path):
    html = f"""<body><p>Welcome</p>{BOT}
    <script>bp.init({{greeting: "Hi, I'm Juno, an AI assistant. Ask me anything."}})</script></body>"""
    result = scan_html(tmp_path, html)
    assert ids(result) == {("PAGE-003", Status.PASS)}
    assert result.findings[0].location == "widget configuration"


@pytest.mark.parametrize(
    "hidden",
    [
        '<p style="display:none">This chat is powered by AI.</p>',
        '<p hidden>This chat is powered by AI.</p>',
        '<p aria-hidden="true">This chat is powered by AI.</p>',
        '<p class="sr-only">This chat is powered by AI.</p>',
        "<noscript>This chat is powered by AI.</noscript>",
        '<button aria-label="Chat with our AI assistant">Chat</button>',
        '<div style="display:none"><div><p>This chat is powered by AI.</p></div></div>',
    ],
)
def test_hidden_notices_are_not_visible_notices(tmp_path, hidden):
    result = scan_html(tmp_path, f"<body><p>Welcome</p>{hidden}{BOT}</body>")
    assert ids(result) == {("PAGE-004", Status.REVIEW)}


def test_overflow_hidden_class_does_not_hide_text(tmp_path):
    html = f'<body><div class="overflow-hidden"><p>You are chatting with our AI assistant.</p></div>{BOT}</body>'
    assert ids(scan_html(tmp_path, html)) == {("PAGE-003", Status.PASS)}


def test_text_after_a_hidden_block_is_visible_again(tmp_path):
    html = f'<body><div hidden><p>x</p></div><p>You are chatting with our AI assistant.</p>{BOT}</body>'
    assert ids(scan_html(tmp_path, html)) == {("PAGE-003", Status.PASS)}


def test_script_and_style_text_is_never_page_text(tmp_path):
    html = f"<body><style>.ai-generated{{color:red}}</style><script>var note='AI-generated';</script><p>Hi</p>{BOT}</body>"
    page = web.parse_html(html)
    assert page.visible_text == "Hi"


def test_voice_widget_by_custom_element(tmp_path):
    result = scan_html(tmp_path, '<body><elevenlabs-convai agent-id="x"></elevenlabs-convai></body>')
    assert ids(result) == {("PAGE-001", Status.REVIEW)}
    assert "spoken" in result.findings[0].detail


def test_ai_declarations_in_code(tmp_path):
    for marker in [
        '<meta name="ai-generated" content="true">',
        '<article data-ai-generated="true"><p>Text</p></article>',
        '<script type="application/ld+json">{"@type":"Article","digitalSourceType":"https://schema.org/TrainedAlgorithmicMediaDigitalSource"}</script>',
    ]:
        result = scan_html(tmp_path, f"<html><head>{marker}</head><body><p>News</p></body></html>")
        assert ("LBL-003", Status.REVIEW) in ids(result), marker
    labelled = scan_html(tmp_path, '<head><meta name="ai-generated" content="true"></head><body><p>This article was generated with AI.</p></body>')
    assert ("LBL-003", Status.REVIEW) not in ids(labelled)
    off = scan_html(tmp_path, '<head><meta name="ai-generated" content="false"></head><body><p>News</p></body>')
    assert ("LBL-003", Status.REVIEW) not in ids(off)


def test_inline_data_image_is_inspected(tmp_path):
    import base64

    data = (SITES / "northwind-bad" / "img" / "hero.png").read_bytes()
    uri = "data:image/png;base64," + base64.b64encode(data).decode()
    result = scan_html(tmp_path, f'<body><img src="{uri}"><p>Hello</p></body>')
    assert ("LBL-001", Status.REVIEW) in ids(result)


def test_no_media_flag_and_cap(tmp_path):
    result = web.scan(str(SITES / "northwind-bad"), check_media=False)
    assert result.facts["media_inspected"] == 0
    assert ("LBL-001", Status.REVIEW) not in ids(result)
    capped = web.scan(str(SITES / "northwind-bad"), max_media=1)
    assert capped.facts["media_inspected"] == 1 and capped.facts["media_not_inspected"] == 1


def test_missing_file_is_an_error():
    result = web.scan("/no/such/page.html")
    assert result.error and not result.findings


# --- over HTTP, against a local server -------------------------------------


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    root = tmp_path / "www"
    root.mkdir()
    for name in ("northwind-bad", "northwind-good"):
        site = root / name
        (site / "img").mkdir(parents=True)
        (site / "index.html").write_bytes((SITES / name / "index.html").read_bytes())
        for image in (SITES / name / "img").iterdir():
            (site / "img" / image.name).write_bytes(image.read_bytes())

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(root))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", root
    httpd.shutdown()


def test_scan_over_http_resolves_relative_images(server):
    base, _ = server
    result = web.scan(f"{base}/northwind-bad/")
    assert ids(result) == {("PAGE-001", Status.REVIEW), ("LBL-001", Status.REVIEW)}
    assert result.facts["media_inspected"] == 2


def test_robots_txt_is_respected_unless_overridden(server):
    base, root = server
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /northwind-good/\n")
    blocked = web.scan(f"{base}/northwind-good/")
    assert "robots.txt" in blocked.error
    allowed = web.scan(f"{base}/northwind-bad/")
    assert not allowed.error
    forced = web.scan(f"{base}/northwind-good/", web.Fetcher(respect_robots=False))
    assert ids(forced) == {("PAGE-003", Status.PASS), ("LBL-002", Status.PASS)}


def test_http_errors_are_reported(server):
    base, _ = server
    result = web.scan(f"{base}/missing/")
    assert "404" in result.error
