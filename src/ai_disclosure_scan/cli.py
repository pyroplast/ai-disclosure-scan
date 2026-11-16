"""Command-line entry point."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, media, report, rules, transcript, web
from .models import Report, Status

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

_DESCRIPTION = """\
Technical readiness signals for the transparency duties in Article 50 of the EU AI Act.

  page        scan a web page (URL or .html file) for chat widgets, AI notices and AI-made media
  transcript  scan chatbot conversations: does the assistant say it is an AI, and when?
  media       scan image, audio and video files for machine-readable AI marking
  rules       print the rule catalogue

Not legal advice. Signals only: a person still has to decide what applies to your system.
"""


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-f", "--format", choices=sorted(report.RENDERERS), default="text", help="report format (default: text)")
    common.add_argument("-o", "--output", metavar="FILE", help="write the report to FILE instead of stdout")
    common.add_argument(
        "--fail-on",
        choices=["gap", "review", "never"],
        default="gap",
        help="exit with status 1 when findings of this level exist (default: gap)",
    )

    parser = argparse.ArgumentParser(
        prog="ai-disclosure-scan",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"ai-disclosure-scan {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    page = sub.add_parser("page", parents=[common], help="scan web pages")
    page.add_argument("targets", nargs="+", metavar="URL_OR_FILE")
    page.add_argument("--no-media", action="store_true", help="do not download and inspect media on the page")
    page.add_argument("--max-media", type=int, default=12, metavar="N", help="inspect at most N media files per page (default: 12)")
    page.add_argument("--timeout", type=float, default=15.0, metavar="SECONDS", help="network timeout (default: 15)")
    page.add_argument("--ignore-robots", action="store_true", help="fetch even when robots.txt disallows it")

    convo = sub.add_parser("transcript", parents=[common], help="scan chatbot conversations")
    convo.add_argument("targets", nargs="+", metavar="FILE_OR_DIR")
    convo.add_argument(
        "--ui-notice",
        action="store_true",
        help="the chat UI itself shows a visible AI notice before the first reply; skip the first-message check",
    )

    files = sub.add_parser("media", parents=[common], help="scan media files")
    files.add_argument("targets", nargs="+", metavar="FILE_OR_DIR")

    listing = sub.add_parser("rules", help="print the rule catalogue")
    listing.add_argument("-f", "--format", choices=["text", "json", "md"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_ERROR
    if args.command == "rules":
        return _print_rules(args.format)

    results = []
    if args.command == "page":
        fetcher = web.Fetcher(timeout=args.timeout, respect_robots=not args.ignore_robots)
        for target in args.targets:
            results.append(web.scan(target, fetcher, check_media=not args.no_media, max_media=args.max_media))
    elif args.command == "transcript":
        for target in args.targets:
            results.extend(_missing(target, "transcript") or transcript.scan_path(Path(target), ui_notice=args.ui_notice))
    elif args.command == "media":
        for target in args.targets:
            results.extend(_missing(target, "media") or media.scan_path(Path(target)))

    scan_report = Report(
        tool_version=__version__,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        results=results,
    )

    if args.format == "text":
        use_color = not args.output and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        text = report.to_text(scan_report, color=use_color)
    else:
        text = report.RENDERERS[args.format](scan_report)

    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
        print(report.summary_line(scan_report), file=sys.stderr)
    else:
        print(text)

    return _exit_code(scan_report, args.fail_on)


def _missing(target: str, kind: str):
    from .models import TargetResult

    if Path(target).exists():
        return None
    return [TargetResult(target, kind, error="no such file or folder")]


def _exit_code(scan_report: Report, fail_on: str) -> int:
    if scan_report.results and scan_report.errors() == len(scan_report.results):
        return EXIT_ERROR  # nothing could be scanned at all
    counts = scan_report.counts()
    if fail_on == "gap" and counts[Status.GAP.value]:
        return EXIT_FINDINGS
    if fail_on == "review" and (counts[Status.GAP.value] or counts[Status.REVIEW.value]):
        return EXIT_FINDINGS
    return EXIT_OK


def _print_rules(fmt: str) -> int:
    if fmt == "json":
        import json

        print(json.dumps([rule.to_dict() for rule in rules.all_rules()], indent=2, ensure_ascii=False))
        return EXIT_OK
    if fmt == "md":
        print(rules.to_markdown())
        return EXIT_OK
    for rule in rules.all_rules():
        print(f"{rule.id}  Art. {rule.paragraph}  ({rule.duty_holder})")
        print(f"  {rule.title}")
        print(f"  Why: {rule.why}")
        print(f"  Fix: {rule.fix}")
        print("  Basis:")
        for basis in rule.basis:
            src = rules.SOURCES[basis.source]
            print(f"    - [{src.weight}] {basis.pinpoint}: {basis.says}")
            print(f"      {src.url}")
        print(f"  Scanner's reading: {rule.reading}")
        print()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
