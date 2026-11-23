"""The Python API returns the same findings as the CLI, plus the evidence behind them."""

import hashlib
import json
import threading
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ai_disclosure_scan import __version__, api, media, transcript, web

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
FIXED = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def _summary(report):
    return [
        (r.target, r.error, [(f.rule_id, f.status.value, f.location, f.evidence) for f in r.findings])
        for r in report.results
    ]


@pytest.fixture
def served_examples():
    handler = partial(SimpleHTTPRequestHandler, directory=str(EXAMPLES))
    handler.log_message = lambda *a, **k: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_pages_match_the_cli_path_and_return_the_html_and_media():
    target = str(EXAMPLES / "sites" / "northwind-bad")
    result = api.scan_pages([target], generated_at=FIXED)

    assert _summary(result.report) == _summary_of([web.scan(target)])
    kinds = sorted((e.kind, Path(e.name).name) for e in result.evidence)
    assert kinds == [("html", "index.html"), ("media", "hero.png"), ("media", "team.png")]
    html = next(e for e in result.evidence if e.kind == "html")
    assert html.data == (EXAMPLES / "sites" / "northwind-bad" / "index.html").read_bytes()
    assert all(e.target == target for e in result.evidence)


def test_pages_over_http_keep_the_bytes_as_served(served_examples):
    url = served_examples + "/sites/northwind-good/"
    result = api.scan_pages([url], respect_robots=False, generated_at=FIXED)
    (page,) = result.report.results
    assert page.error == ""
    assert {f.rule_id for f in page.findings} == {"PAGE-003", "LBL-002"}
    html = next(e for e in result.evidence if e.kind == "html")
    assert html.name == url
    assert html.media_type.startswith("text/html")
    assert html.data == (EXAMPLES / "sites" / "northwind-good" / "index.html").read_bytes()


def test_transcripts_match_scan_path_and_return_each_file():
    folder = EXAMPLES / "transcripts"
    result = api.scan_transcripts([folder], generated_at=FIXED)
    assert _summary(result.report) == _summary_of(transcript.scan_path(folder))
    files = sorted(p for p in folder.iterdir() if p.suffix in transcript.TRANSCRIPT_SUFFIXES)
    assert [Path(e.name) for e in result.evidence] == files
    for item in result.evidence:
        assert item.kind == "transcript"
        assert item.data == Path(item.name).read_bytes()


def test_transcript_bytes_with_crlf_match_the_file_reader(tmp_path):
    text = (EXAMPLES / "transcripts" / "03-claims-to-be-human.txt").read_text(encoding="utf-8")
    crlf = tmp_path / "crlf.txt"
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    from_file = transcript.analyze(transcript.load(crlf)[0], str(crlf))
    (from_bytes,) = transcript.scan_bytes(crlf.read_bytes(), str(crlf), ".txt")
    assert [(f.rule_id, f.location) for f in from_bytes.findings] == [
        (f.rule_id, f.location) for f in from_file.findings
    ]


def test_media_match_scan_path_and_return_each_file():
    folder = EXAMPLES / "media"
    result = api.scan_media([folder], generated_at=FIXED)
    assert _summary(result.report) == _summary_of(media.scan_path(folder))
    assert {f.rule_id for _, f in result.report.all_findings()} >= {"MED-001", "MED-002"}
    for item in result.evidence:
        assert hashlib.sha256(item.data).hexdigest() == hashlib.sha256(Path(item.name).read_bytes()).hexdigest()


def test_missing_paths_become_error_results():
    result = api.scan_media(["/no/such/folder"], generated_at=FIXED)
    (only,) = result.report.results
    assert only.error == "no such file or folder"
    assert result.evidence == []


def test_json_is_the_cli_json_and_deterministic_with_a_fixed_time():
    first = api.scan_transcripts([EXAMPLES / "transcripts"], generated_at=FIXED).to_json()
    second = api.scan_transcripts([EXAMPLES / "transcripts"], generated_at=FIXED).to_json()
    assert first == second
    data = json.loads(first)
    assert data["version"] == __version__ == api.scanner_version()
    assert data["generated_at"] == "2026-08-03 09:00 UTC"


def test_naive_generated_at_is_rejected():
    with pytest.raises(ValueError):
        api.scan_media([EXAMPLES / "media"], generated_at=datetime(2026, 8, 3))


def test_rule_basis_is_the_catalogue_entry():
    basis = api.rule_basis("INT-002")
    assert basis["id"] == "INT-002"
    assert basis["paragraph"]
    assert basis["basis"] and all(b["url"].startswith("https://") for b in basis["basis"])
    with pytest.raises(KeyError):
        api.rule_basis("NOPE-999")


def _summary_of(results):
    from ai_disclosure_scan.models import Report

    return _summary(Report(__version__, "", list(results)))
