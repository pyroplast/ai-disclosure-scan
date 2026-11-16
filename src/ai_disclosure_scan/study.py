"""Run browser mode over a list of sites and publish only the totals.

The output folder gets two kinds of file:

    private/   one JSON per site, with the URL and what its widget said.
               For checking the numbers yourself. Do not publish.
    summary.md the aggregate, with no site names, no URLs and no quotes.
               This is the part meant for a post.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, web
from .models import TargetResult

OUTCOMES = [
    ("says_ai", "Says it is an AI when opened"),
    ("generic_label", "Only a generic label (e.g. 'virtual assistant')"),
    ("claims_human", "Claims to be a person"),
    ("silent_ai_product", "Says nothing about AI (AI-first chat product)"),
    ("silent_chat_platform", "Says nothing about AI (live-chat platform, may be human-staffed)"),
    ("not_opened", "Widget found but could not be opened"),
]


def read_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            urls.append(line if re.match(r"[a-z][a-z0-9+.-]*://", line, re.I) else "https://" + line)
    return list(dict.fromkeys(urls))


def outcome(result: TargetResult) -> str:
    """Put one site into exactly one bucket."""
    if result.error:
        return "error"
    ids = {f.rule_id: f for f in result.findings}
    if "BRW-003" in ids:
        return "claims_human"
    if "BRW-010" in ids:
        return "says_ai"
    if "BRW-002" in ids:
        return "generic_label"
    if "BRW-001" in ids:
        return "silent_ai_product" if ids["BRW-001"].status.value == "gap" else "silent_chat_platform"
    if "BRW-004" in ids:
        return "not_opened"
    return "no_widget"


def run(urls: list[str], out: Path, fetcher: web.Fetcher, delay: float = 5.0, timeout: float = 30.0, log=print) -> dict:
    from . import browser

    out.mkdir(parents=True, exist_ok=True)
    private = out / "private"
    private.mkdir(exist_ok=True)
    (private / "README.txt").write_text("Per-site results with URLs and widget text. Do not publish.\n", encoding="utf-8")

    rows = []
    for n, url in enumerate(urls, 1):
        log(f"[{n}/{len(urls)}] {url}")
        result = web.scan(url, fetcher, check_media=False, use_browser=True, browser_timeout=timeout)
        bucket = outcome(result)
        kinds = sorted({w["kind"] for w in result.facts.get("widgets", [])})
        rows.append({"bucket": bucket, "kinds": kinds, "persona": bool(result.facts.get("persona_name"))})
        record = {"url": url, "outcome": bucket, **result.to_dict()}
        (private / f"{n:03d}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"        -> {bucket}")
        if n < len(urls):
            browser.pause(delay)

    summary = summarise(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "summary.md").write_text(to_markdown(summary), encoding="utf-8")
    return summary


def summarise(rows: list[dict]) -> dict:
    counts = Counter(r["bucket"] for r in rows)
    with_widget = [r for r in rows if r["bucket"] not in {"no_widget", "error"}]
    opened = [r for r in with_widget if r["bucket"] != "not_opened"]
    return {
        "tool": f"ai-disclosure-scan {__version__}",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sites": len(rows),
        "errors": counts.get("error", 0),
        "no_widget": counts.get("no_widget", 0),
        "with_widget": len(with_widget),
        "opened": len(opened),
        "outcomes": {key: counts.get(key, 0) for key, _ in OUTCOMES},
        "persona_names_among_opened": sum(1 for r in opened if r["persona"]),
    }


def _pct(n: int, d: int) -> str:
    return f"{round(100 * n / d)}%" if d else "n/a"


def to_markdown(s: dict) -> str:
    opened = s["opened"]
    lines = [
        "# Chat widget AI disclosure: aggregate results",
        "",
        f"{s['sites']} sites visited on {s['date']} with {s['tool']} in browser mode. "
        f"{s['with_widget']} had a chat widget; {opened} of those opened.",
        "",
        "| What the widget showed when opened | Sites | Share of opened |",
        "|---|---:|---:|",
    ]
    for key, label in OUTCOMES:
        if key == "not_opened":
            continue
        n = s["outcomes"][key]
        lines.append(f"| {label} | {n} | {_pct(n, opened)} |")
    lines += [
        "",
        f"- Widgets that could not be opened: {s['outcomes']['not_opened']}",
        f"- Sites with no widget recognised: {s['no_widget']}",
        f"- Sites that could not be loaded: {s['errors']}",
        f"- Opened widgets that introduce themselves with a human first name: {s['persona_names_among_opened']}",
        "",
        "## Method and limits",
        "",
        "- One visit per site, headless Chromium, English locale, no cookies accepted, no message typed.",
        "- 'Says nothing about AI' means no AI wording in the text that appeared when the widget opened. A notice "
        "shown after the visitor types, or drawn as an image, is missed.",
        "- Live-chat platforms can be staffed by people, so a silent widget there is not evidence of an undisclosed AI.",
        "- This is a technical observation of what a visitor sees, not a legal assessment of any site. "
        "Sites are deliberately not named.",
        "",
    ]
    return "\n".join(lines)
