"""Browser mode against fake widgets served from a local folder.

The fake pages reference real vendor script URLs so the widget is recognised,
but the network is not needed: those scripts fail to load and the page's own
inline script draws the widget (in shadow DOM, like real widgets do).
"""

import json
from pathlib import Path

import pytest

from ai_disclosure_scan import browser, cli, study, web
from ai_disclosure_scan.models import Status

WIDGETS = Path(__file__).resolve().parent / "fixtures" / "widgets"


def _can_launch():
    ok, _ = browser.available()
    if not ok:
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser._launch(pw).close()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _can_launch(), reason="Playwright with a Chromium browser is not available")


def scan(name):
    return web.scan(str(WIDGETS / name), check_media=False, use_browser=True, browser_timeout=15)


def ids(result):
    return {(f.rule_id, f.status) for f in result.findings}


def test_silent_ai_widget_is_a_gap():
    result = scan("silent.html")
    assert ids(result) == {("BRW-001", Status.GAP)}
    assert result.facts["persona_name"] == "Sarah"
    assert result.facts["browser"]["widget_opened"] is True
    assert "clicked" in result.facts["browser"]["open_method"]


def test_disclosing_widget_passes():
    result = scan("discloses.html")
    assert ids(result) == {("BRW-010", Status.PASS)}
    assert "AI assistant" in result.findings[0].evidence


def test_widget_claiming_to_be_human():
    assert ids(scan("human.html")) == {("BRW-003", Status.GAP)}


def test_vendor_api_opener_and_generic_label():
    result = scan("api.html")
    assert ids(result) == {("BRW-002", Status.REVIEW)}
    assert result.facts["browser"]["open_method"] == "Botpress JavaScript API"


def test_widget_that_cannot_be_opened_keeps_the_static_finding():
    result = scan("nolauncher.html")
    assert ("BRW-004", Status.REVIEW) in ids(result)
    assert ("PAGE-001", Status.REVIEW) in ids(result)


def test_silent_live_chat_platform_is_review_not_gap():
    assert ids(scan("livechat.html")) == {("BRW-001", Status.REVIEW)}


def test_notice_drawn_by_javascript_is_seen_only_in_browser_mode():
    static = web.scan(str(WIDGETS / "jsnotice.html"), check_media=False)
    assert ("PAGE-001", Status.REVIEW) in ids(static)
    rendered = scan("jsnotice.html")
    assert ("PAGE-003", Status.PASS) in ids(rendered)


def test_study_publishes_totals_without_names(tmp_path, capsys):
    url_file = tmp_path / "sites.txt"
    pages = ["silent.html", "discloses.html", "human.html", "livechat.html", "nolauncher.html"]
    url_file.write_text("# test list\n" + "\n".join((WIDGETS / p).as_uri() for p in pages) + "\n")
    out = tmp_path / "study"
    code = cli.main(["study", str(url_file), "-o", str(out), "--delay", "0", "--timeout", "15"])
    assert code == 0
    summary = json.loads((out / "summary.json").read_text())
    assert summary["sites"] == 5 and summary["with_widget"] == 5 and summary["opened"] == 4
    assert summary["outcomes"] == {
        "says_ai": 1, "generic_label": 0, "claims_human": 1,
        "silent_ai_product": 1, "silent_chat_platform": 1, "not_opened": 1,
    }  # fmt: skip
    public = (out / "summary.md").read_text()
    for p in pages:
        assert p not in public  # no site names or URLs in the publishable file
    assert "Sarah" not in public
    assert len(list((out / "private").glob("*.json"))) == 5


def test_read_urls_adds_scheme_and_dedupes(tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("example.com\nhttps://example.com\n# comment\n\nhttp://x.test  # trailing\n")
    assert study.read_urls(f) == ["https://example.com", "http://x.test"]


def test_falls_back_to_clicking_when_the_vendor_api_shows_nothing():
    result = scan("deadapi.html")
    assert ids(result) == {("BRW-010", Status.PASS)}
    assert result.facts["browser"]["open_method"].startswith("clicked")


def scan_with(name, **kwargs):
    return web.scan(str(WIDGETS / name), check_media=False, use_browser=True, browser_timeout=15, **kwargs)


def test_widget_behind_cookie_banner_needs_consent():
    without = scan_with("consent.html")
    assert ("PAGE-005", Status.INFO) in ids(without)
    assert not any(f.rule_id.startswith("BRW") for f in without.findings)
    accepted = scan_with("consent.html", accept_cookies=True)
    assert ids(accepted) == {("BRW-010", Status.PASS)}
    assert accepted.facts["browser"]["cookie_banner_accepted"] == "button “Aceptar todo”"


def test_contact_page_fallback():
    home_only = scan_with("home-no-chat.html")
    assert ids(home_only) == {("PAGE-005", Status.INFO)}
    followed = scan_with("home-no-chat.html", follow_contact=True)
    assert ids(followed) == {("BRW-001", Status.GAP), ("TGT-003", Status.INFO)}
    assert followed.facts["browser"]["contact_page"].endswith("contacto.html")
    assert followed.final_url.endswith("home-no-chat.html")
    assert followed.analysed_url.endswith("contacto.html")
    gap = next(f for f in followed.findings if f.rule_id == "BRW-001")
    assert "evaluated on" in gap.location and "contacto.html" in gap.location


def test_help_button_that_navigates_is_not_a_widget(tmp_path):
    page = tmp_path / "a.html"
    other = tmp_path / "b.html"
    other.write_text("<html><body><p>Another page with lots of new text.</p></body></html>")
    page.write_text(
        '<html><head><script src="https://cdn.botpress.cloud.invalid/x.js"></script></head>'
        '<body><button aria-label="help" onclick="location.href=\'b.html\'">?</button></body></html>'
    )
    result = web.scan(str(page), check_media=False, use_browser=True, browser_timeout=15)
    assert ("BRW-004", Status.REVIEW) in ids(result)
    assert "navigated away" in result.facts["browser"]["open_method"]


def test_evidence_hook_gets_rendered_html_and_a_screenshot():
    got = []
    result = web.scan(
        str(WIDGETS / "discloses.html"),
        check_media=False,
        use_browser=True,
        browser_timeout=15,
        on_evidence=lambda *item: got.append(item),
        screenshot=True,
    )
    kinds = [kind for kind, _, _, _ in got]
    assert kinds == ["html", "screenshot"]
    html = got[0][2].decode("utf-8")
    assert "<html" in html.lower()
    assert got[1][2].startswith(b"\x89PNG")
    assert got[1][3] == "image/png"
    # Asking for evidence does not change the findings.
    assert ids(result) == ids(scan("discloses.html"))
