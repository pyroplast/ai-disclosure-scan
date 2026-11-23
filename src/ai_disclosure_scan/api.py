"""Stable Python API for programs that embed the scanner.

The CLI, the MCP server and this module run the same checks. This module adds two
things a program needs and a terminal does not:

* the result as a ``Report`` object (``ScanResult.report``) and as the exact JSON that
  ``-f json`` prints (``ScanResult.to_json()``);
* the **evidence**: the bytes each finding was computed from. For pages that is the
  HTML as fetched (or, in browser mode, the rendered DOM), every media file the label
  check inspected, and in browser mode a full-page screenshot taken after the widget
  was opened. For transcripts and media it is each file as read. A program can hash
  and keep these, so a finding can later be traced to the content behind it.

Nothing here changes what the checks find. Names in this module are kept stable
across minor versions.

    from ai_disclosure_scan import api

    result = api.scan_pages(["https://example.com/"], browser=True)
    for target, finding in result.report.all_findings():
        print(finding.rule_id, finding.status.value, api.rule_basis(finding.rule_id)["paragraph"])
    for item in result.evidence:
        print(item.kind, item.name, len(item.data))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

from . import __version__, media, report, rules, transcript, web
from .models import Report, TargetResult

__all__ = [
    "Evidence",
    "ScanResult",
    "rule_basis",
    "scan_media",
    "scan_pages",
    "scan_transcripts",
    "scanner_version",
]

PathLike = Union[str, Path]


@dataclass(frozen=True)
class Evidence:
    """One piece of content a scan analysed.

    target      the ``TargetResult.target`` it belongs to
    kind        "html", "screenshot", "media" (page scans); "transcript"; "media"
    name        where it came from: the URL or path, or the ``src`` of a page's media
    data        the bytes, exactly as analysed (capped at the scanner's size limits)
    media_type  the Content-Type when known, else ""
    """

    target: str
    kind: str
    name: str
    data: bytes = field(repr=False)
    media_type: str = ""


@dataclass
class ScanResult:
    report: Report
    evidence: list = field(default_factory=list)  # list[Evidence]

    def to_json(self) -> str:
        """The report as ``ai-disclosure-scan ... -f json`` prints it."""
        return report.to_json(self.report)


def scanner_version() -> str:
    return __version__


def rule_basis(rule_id: str) -> dict:
    """The catalogue entry for a rule: paragraph, duty holder, title, why, fix, the
    pinpoint legal basis with source links, and the scanner's own reading.

    Raises KeyError for an unknown rule id.
    """
    return rules.get(rule_id).to_dict()


def scan_pages(
    targets: Iterable[str],
    *,
    check_media: bool = True,
    max_media: int = 12,
    timeout: float = 15.0,
    respect_robots: bool = True,
    browser: bool = False,
    accept_cookies: bool = False,
    follow_contact: bool = False,
    screenshot: bool = True,
    generated_at: Optional[datetime] = None,
) -> ScanResult:
    """Scan web pages (URLs or local .html files / folders), like ``ai-disclosure-scan page``."""
    fetcher = web.Fetcher(timeout=timeout, respect_robots=respect_robots)
    evidence: list[Evidence] = []
    results: list[TargetResult] = []
    for target in targets:

        def hook(kind: str, name: str, data: bytes, media_type: str, _target: str = target) -> None:
            evidence.append(Evidence(_target, kind, name, data, media_type))

        results.append(
            web.scan(
                target,
                fetcher,
                check_media=check_media,
                max_media=max_media,
                use_browser=browser,
                browser_timeout=max(timeout, 30.0),
                accept_cookies=accept_cookies,
                follow_contact=follow_contact,
                on_evidence=hook,
                screenshot=screenshot,
            )
        )
    return ScanResult(_report(results, generated_at), evidence)


def scan_transcripts(
    paths: Iterable[PathLike],
    *,
    ui_notice: bool = False,
    generated_at: Optional[datetime] = None,
) -> ScanResult:
    """Scan chatbot transcript files or folders, like ``ai-disclosure-scan transcript``."""
    evidence: list[Evidence] = []
    results: list[TargetResult] = []
    for path in paths:
        files, error = _files(Path(path), transcript.TRANSCRIPT_SUFFIXES, "transcript")
        if error is not None:
            results.append(error)
            continue
        for file in files:
            try:
                data = file.read_bytes()
            except OSError as exc:
                results.append(TargetResult(str(file), "transcript", error=str(exc)))
                continue
            evidence.append(Evidence(str(file), "transcript", str(file), data))
            results.extend(transcript.scan_bytes(data, str(file), file.suffix, ui_notice=ui_notice))
    return ScanResult(_report(results, generated_at), evidence)


def scan_media(
    paths: Iterable[PathLike],
    *,
    generated_at: Optional[datetime] = None,
) -> ScanResult:
    """Scan image, audio and video files or folders, like ``ai-disclosure-scan media``."""
    evidence: list[Evidence] = []
    results: list[TargetResult] = []
    for path in paths:
        files, error = _files(Path(path), media.MEDIA_SUFFIXES, "media")
        if error is not None:
            results.append(error)
            continue
        for file in files:
            try:
                data, truncated = media.read_limited(file)
            except OSError as exc:
                results.append(TargetResult(str(file), "media", error=str(exc)))
                continue
            evidence.append(Evidence(str(file), "media", str(file), data))
            results.append(media.scan_bytes(data, str(file), truncated))
    return ScanResult(_report(results, generated_at), evidence)


def _files(path: Path, suffixes: Iterable[str], kind: str):
    """The files a folder scan visits, in the same order as the CLI, or an error result."""
    if not path.exists():
        return [], TargetResult(str(path), kind, error="no such file or folder")
    if path.is_dir():
        wanted = {s.lower() for s in suffixes}
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in wanted)
        if not files:
            label = "transcript" if kind == "transcript" else "media"
            return [], TargetResult(str(path), kind, error=f"no {label} files found in this folder")
        return files, None
    return [path], None


def _report(results: list, generated_at: Optional[datetime]) -> Report:
    when = generated_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return Report(
        tool_version=__version__,
        generated_at=when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        results=results,
    )
