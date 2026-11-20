"""Report formats: terminal text, JSON, Markdown and a single-file HTML page."""

from __future__ import annotations

import json
from collections import Counter
from html import escape

from . import rules
from .models import STATUS_ORDER, Report, Status, TargetResult

SCOPE = (
    "Scope: machine-observable technical signals for the transparency duties in Article 50 of the EU AI Act "
    "(Regulation (EU) 2024/1689). Not legal advice, and not a conformity assessment or certification."
)

DISCLAIMER = (
    SCOPE + " Whether a duty applies to you, and whether you meet it, needs a person who knows your system."
)

LEGAL_BASIS = {
    "regulation": "Regulation (EU) 2024/1689 (EU AI Act), Article 50",
    "text": rules.SOURCES["act"].url,
    "applies_since": "2026-08-02",
    "note": (
        "For systems placed on the market before 2026-08-02, the marking and detection duty in "
        "Article 50(2) applies from 2026-12-02 (Commission FAQ on Article 50)."
    ),
    "note_source": rules.SOURCES["faq"].url,
}


def _art(rule: rules.Rule) -> str:
    return "scan note" if rule.kind == "scan-note" else f"Art. {rule.paragraph}"


def _provenance(result: TargetResult) -> list[str]:
    """For page scans: what was asked for, where it landed, and what was analysed."""
    if result.kind != "page":
        return []
    requested = result.requested_url or result.target
    out = [f"requested: {requested}"]
    if result.final_url:
        out.append(f"final:     {result.final_url}")
    if result.analysed_url and result.analysed_url != result.final_url:
        out.append(f"analysed:  {result.analysed_url}")
    return out


def _used_rules(report: Report) -> list[rules.Rule]:
    used = {f.rule_id for _, f in report.all_findings()}
    return [rule for rule in rules.all_rules() if rule.id in used]


def _basis_refs(rule: rules.Rule) -> str:
    """Just the places in the Act itself, e.g. 'Article 50(1), first sentence · Article 50(5), first sentence'."""
    refs = [b.pinpoint for b in rule.basis if rules.SOURCES[b.source].weight == "law"]
    return " · ".join(refs)


def _basis_short(rule: rules.Rule) -> str:
    if not rule.basis:
        return "scan note, not an Article 50 check"
    return "; ".join(f"{b.pinpoint} [{rules.SOURCES[b.source].weight}]" for b in rule.basis)

_LABEL = {Status.GAP: "GAP", Status.REVIEW: "REVIEW", Status.PASS: "PASS", Status.INFO: "INFO"}
_WORD = {Status.GAP: "gaps", Status.REVIEW: "to review", Status.PASS: "passed", Status.INFO: "info"}
_ANSI = {Status.GAP: "31;1", Status.REVIEW: "33;1", Status.PASS: "32;1", Status.INFO: "36"}


def summary_line(report: Report) -> str:
    counts = report.counts()
    parts = [f"{counts[s.value]} {_WORD[s]}" for s in STATUS_ORDER]
    line = " · ".join(parts) + f"   ({len(report.results)} scanned"
    if report.errors():
        line += f", {report.errors()} could not be read"
    return line + ")"


def _sorted_findings(result: TargetResult):
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    return sorted(result.findings, key=lambda f: order[f.status])


def top_issues(report: Report) -> list[tuple[Status, str, int]]:
    """Gap and review rules, most frequent first: what to look at before anything else."""
    counter: Counter[tuple[Status, str]] = Counter()
    for _, finding in report.all_findings():
        if finding.status in (Status.GAP, Status.REVIEW):
            counter[(finding.status, finding.rule_id)] += 1
    order = {Status.GAP: 0, Status.REVIEW: 1}
    ranked = sorted(counter.items(), key=lambda item: (order[item[0][0]], -item[1], item[0][1]))
    return [(status, rule_id, n) for (status, rule_id), n in ranked]


# ---------------------------------------------------------------------------
# Terminal
# ---------------------------------------------------------------------------


def to_text(report: Report, color: bool = False) -> str:
    def paint(status: Status) -> str:
        label = f"{_LABEL[status]:<6}"
        return f"\033[{_ANSI[status]}m{label}\033[0m" if color else label

    lines = [f"ai-disclosure-scan {report.tool_version} · EU AI Act Article 50 readiness signals", ""]
    for result in report.results:
        lines.append(f"{result.target}  ({result.kind})")
        lines.extend(f"  {line}" for line in _provenance(result))
        if result.error:
            lines.append(f"  could not scan: {result.error}")
        for finding in _sorted_findings(result):
            rule = rules.get(finding.rule_id)
            where = f"  @ {finding.location}" if finding.location else ""
            lines.append(f"  {paint(finding.status)} {rule.id}  {rule.title}  [{_art(rule)}]{where}")
            lines.append(f"         {finding.detail}")
            if finding.evidence:
                lines.append(f"         evidence: {finding.evidence}")
            if finding.status in (Status.GAP, Status.REVIEW):
                lines.append(f"         fix: {rule.fix}")
            lines.append(f"         basis: {_basis_short(rule)}")
        lines.append("")
    lines.append("Summary: " + summary_line(report))
    lines.append("")
    lines.append("Legal basis of the checks above (open the links to compare with the source)")
    for rule in _used_rules(report):
        lines.append(f"  {rule.id}  {rule.title}")
        for basis in rule.basis:
            src = rules.SOURCES[basis.source]
            lines.append(f"    - [{src.weight}] {basis.pinpoint}: {basis.says}")
            lines.append(f"      {src.url}")
        label = "About this note" if rule.kind == "scan-note" else "Scanner's reading (not the law)"
        lines.append(f"    {label}: {rule.reading}")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def to_json(report: Report) -> str:
    used = sorted({f.rule_id for _, f in report.all_findings()})
    payload = {
        "tool": "ai-disclosure-scan",
        "version": report.tool_version,
        "generated_at": report.generated_at,
        "legal_basis": LEGAL_BASIS,
        "scope": SCOPE,
        "disclaimer": DISCLAIMER,
        "summary": {**report.counts(), "scanned": len(report.results), "errors": report.errors()},
        "results": [r.to_dict() for r in report.results],
        "rules": {rule_id: rules.get(rule_id).to_dict() for rule_id in used},
        "sources": [
            {"weight": src.weight, "title": src.title, "url": src.url} for src in rules.SOURCES.values()
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def to_markdown(report: Report) -> str:
    counts = report.counts()
    lines = [
        "# AI disclosure scan",
        "",
        f"EU AI Act Article 50 readiness signals · generated {report.generated_at} · ai-disclosure-scan {report.tool_version}",
        "",
        "| Gaps | To review | Passed | Info | Scanned |",
        "|---:|---:|---:|---:|---:|",
        f"| {counts['gap']} | {counts['review']} | {counts['pass']} | {counts['info']} | {len(report.results)} |",
        "",
    ]
    issues = top_issues(report)
    if issues:
        lines += ["## What to look at first", ""]
        for status, rule_id, n in issues:
            rule = rules.get(rule_id)
            lines.append(f"- **{_LABEL[status]}** `{rule.id}` {rule.title} ({_art(rule)}): {n}×")
        lines.append("")
    lines += ["## Findings", ""]
    for result in report.results:
        lines += [f"### `{result.target}` ({result.kind})", ""]
        prov = _provenance(result)
        if prov:
            lines += [f"- {line}" for line in prov] + [""]
        if result.error:
            lines += [f"Could not scan: {result.error}", ""]
        for finding in _sorted_findings(result):
            rule = rules.get(finding.rule_id)
            where = f" at {finding.location}" if finding.location else ""
            lines.append(f"- **{_LABEL[finding.status]}** `{rule.id}` {rule.title} ({_art(rule)}){where}")
            lines.append(f"  - {finding.detail}")
            if finding.evidence:
                lines.append(f"  - Evidence: `{finding.evidence.replace('`', chr(39))}`")
            if finding.status in (Status.GAP, Status.REVIEW):
                lines.append(f"  - Fix: {rule.fix}")
        lines.append("")
    lines += ["## Legal basis of these checks", ""]
    lines.append(
        "Each check names the exact place in its source. Only sources marked *law* bind; "
        "the scanner's reading is this tool's interpretation."
    )
    lines.append("")
    for rule in _used_rules(report):
        lines += [f"**`{rule.id}` {rule.title}**", ""]
        for basis in rule.basis:
            src = rules.SOURCES[basis.source]
            lines.append(f"- *{src.weight}* · [{basis.pinpoint}]({src.url}): {basis.says}")
        label = "About this note" if rule.kind == "scan-note" else "Scanner's reading (not the law)"
        lines += [f"- *{label}:* {rule.reading}", ""]
    lines += ["---", "", DISCLAIMER, ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1b1c1e;--muted:#63666b;--line:#e3e1dc;--code:#f1efea;
--gap:#b42318;--gap-bg:#fdecea;--review:#93520a;--review-bg:#fdf1dc;--pass:#0b6b43;--pass-bg:#e3f4ea;--info:#3d5a80;--info-bg:#e8eef6}
@media (prefers-color-scheme:dark){:root{--bg:#141516;--card:#1d1f21;--ink:#ecebe7;--muted:#a2a5aa;--line:#303236;--code:#26282b;
--gap:#ff8a7a;--gap-bg:#3a1c18;--review:#f2b660;--review-bg:#39290f;--pass:#6fd4a0;--pass-bg:#12301f;--info:#9cbbe6;--info-bg:#1b2a3d}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:900px;margin:0 auto;padding:40px 20px 64px}
header p.kicker{margin:0 0 6px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{margin:0;font-size:34px;line-height:1.15;letter-spacing:-.01em}
header p.meta{margin:10px 0 0;color:var(--muted);font-size:14px}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:28px 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.tile b{display:block;font-size:34px;line-height:1.1;font-variant-numeric:tabular-nums}
.tile span{font-size:13px;color:var(--muted)}
.tile.gap b{color:var(--gap)}.tile.review b{color:var(--review)}.tile.pass b{color:var(--pass)}.tile.info b{color:var(--info)}
h2{font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:36px 0 12px}
.first{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 18px;margin:0;list-style:none}
.first li{display:flex;gap:12px;align-items:baseline;padding:10px 0;border-top:1px solid var(--line)}
.first li:first-child{border-top:0}
.first .n{margin-left:auto;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap}
.target{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:0 0 14px;overflow:hidden}
.target>h3{margin:0;padding:14px 18px;font-size:15px;font-weight:600;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.target>h3 code{font-size:14px;background:none;padding:0;overflow-wrap:anywhere}
.target>h3 small{color:var(--muted);font-weight:400}
.finding{padding:14px 18px;border-top:1px solid var(--line)}
.finding:first-of-type{border-top:0}
.finding .head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.finding .title{font-weight:600}
.ref{color:var(--muted);font-size:13px}
.finding p{margin:6px 0 0}
.finding p.fix{color:var(--muted)}
.pill{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;padding:2px 8px;border-radius:999px;white-space:nowrap}
.pill.gap{color:var(--gap);background:var(--gap-bg)}.pill.review{color:var(--review);background:var(--review-bg)}
.pill.pass{color:var(--pass);background:var(--pass-bg)}.pill.info{color:var(--info);background:var(--info-bg)}
code{font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--code);padding:2px 6px;border-radius:6px;overflow-wrap:anywhere}
.evidence{display:block;margin-top:8px;padding:8px 10px}
.error{padding:14px 18px;color:var(--gap)}
.prov{margin:0;padding:10px 18px;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--muted);border-bottom:1px solid var(--line);overflow-wrap:anywhere}
details{margin-top:10px;font-size:14px}
summary{cursor:pointer;color:var(--muted)}
details ul{margin:8px 0 0;padding-left:18px}
details li{margin:0 0 8px}
details a{color:inherit}
.weight{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
footer a{color:inherit}
footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:13.5px}
footer p{margin:0 0 8px}
@media (max-width:560px){.tiles{grid-template-columns:repeat(2,1fr)}h1{font-size:28px}}
"""


def to_html(report: Report) -> str:
    counts = report.counts()
    e = escape
    out: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>AI disclosure scan</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<header>",
        '<p class="kicker">EU AI Act · Article 50 readiness signals</p>',
        "<h1>AI disclosure scan</h1>",
        f'<p class="meta">{len(report.results)} scanned · generated {e(report.generated_at)} · '
        f"ai-disclosure-scan {e(report.tool_version)}</p>",
        "</header>",
        '<section class="tiles" aria-label="Summary">',
    ]
    tile_names = {Status.GAP: "Gaps", Status.REVIEW: "To review", Status.PASS: "Passed", Status.INFO: "Info"}
    for status in STATUS_ORDER:
        out.append(
            f'<div class="tile {status.value}"><b>{counts[status.value]}</b><span>{tile_names[status]}</span></div>'
        )
    out.append("</section>")

    issues = top_issues(report)
    if issues:
        out.append('<h2>What to look at first</h2><ul class="first">')
        for status, rule_id, n in issues:
            rule = rules.get(rule_id)
            out.append(
                f'<li><span class="pill {status.value}">{_LABEL[status]}</span>'
                f"<span>{e(rule.title)} <span class=\"ref\">{e(rule.id)} · {e(_art(rule))}</span></span>"
                f'<span class="n">{n}×</span></li>'
            )
        out.append("</ul>")

    out.append("<h2>Findings</h2>")
    for result in report.results:
        out.append(f'<section class="target"><h3><code>{e(result.target)}</code><small>{e(result.kind)}</small></h3>')
        prov = _provenance(result)
        if prov:
            out.append('<p class="prov">' + "<br>".join(e(line) for line in prov) + "</p>")
        if result.error:
            out.append(f'<div class="error">Could not scan: {e(result.error)}</div>')
        for finding in _sorted_findings(result):
            rule = rules.get(finding.rule_id)
            where = f" · {e(finding.location)}" if finding.location else ""
            out.append('<div class="finding"><div class="head">')
            out.append(f'<span class="pill {finding.status.value}">{_LABEL[finding.status]}</span>')
            out.append(f'<span class="title">{e(rule.title)}</span>')
            out.append(f'<span class="ref">{e(rule.id)} · {e(_art(rule))} · {e(rule.duty_holder if rule.kind == "check" else "about the scan")}{where}</span>')
            out.append("</div>")
            out.append(f"<p>{e(finding.detail)}</p>")
            if finding.evidence:
                out.append(f'<code class="evidence">{e(finding.evidence)}</code>')
            if finding.status in (Status.GAP, Status.REVIEW):
                out.append(f'<p class="fix"><b>Fix:</b> {e(rule.fix)}</p>')
            if rule.basis:
                out.append(f"<details><summary>Legal basis: {e(_basis_refs(rule))}</summary><ul>")
                for basis in rule.basis:
                    src = rules.SOURCES[basis.source]
                    out.append(
                        f'<li><span class="weight">{e(src.weight)}</span> '
                        f'<a href="{e(src.url)}" target="_blank" rel="noopener">{e(basis.pinpoint)}</a>'
                        f"<br>{e(basis.says)}</li>"
                    )
                out.append(f'<li><span class="weight">scanner\'s reading, not the law</span><br>{e(rule.reading)}</li>')
                out.append("</ul></details>")
            out.append("</div>")
        out.append("</section>")

    out += [
        "<footer>",
        f"<p>{e(DISCLAIMER)}</p>",
        f'<p><a href="{e(LEGAL_BASIS["text"])}">{e(LEGAL_BASIS["regulation"])}</a>, applicable since 2 August 2026. '
        f'{e(LEGAL_BASIS["note"])} Every finding lists the exact sentence of the Act it rests on, with a link.</p>',
        "<p>Static scan: JavaScript is not run, chat widgets are not opened, and invisible watermarks are not detected.</p>",
        "</footer></main></body></html>",
    ]
    return "\n".join(out)


RENDERERS = {"text": to_text, "json": to_json, "md": to_markdown, "html": to_html}
