import json
import re
from pathlib import Path

import pytest

from ai_disclosure_scan import cli, rules

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def run(capsys, *argv):
    code = cli.main([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_exit_codes(capsys):
    assert run(capsys, "transcript", EX / "transcripts" / "01-discloses-up-front.json")[0] == 0
    assert run(capsys, "transcript", EX / "transcripts" / "02-late-disclosure.json")[0] == 1
    assert run(capsys, "transcript", EX / "transcripts" / "02-late-disclosure.json", "--fail-on", "never")[0] == 0
    # review-level findings only fail the run when asked to
    assert run(capsys, "page", EX / "sites" / "northwind-bad")[0] == 0
    assert run(capsys, "page", EX / "sites" / "northwind-bad", "--fail-on", "review")[0] == 1
    # nothing scannable at all is an error, not a pass
    assert run(capsys, "media", "/no/such/file.png")[0] == 2
    assert run(capsys)[0] == 2


def test_text_report_names_the_legal_basis(capsys):
    _, out, _ = run(capsys, "transcript", EX / "transcripts" / "02-late-disclosure.json")
    assert "INT-002" in out and "GAP" in out
    assert "Article 50(5), first sentence [law]" in out
    assert "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50" in out
    assert "Scanner's reading (not the law)" in out
    assert "not legal advice" in out


def test_json_report_is_complete(capsys):
    _, out, _ = run(capsys, "transcript", EX / "transcripts", "--format", "json")
    data = json.loads(out)
    assert data["summary"]["scanned"] == 9
    assert data["summary"]["gap"] == sum(1 for r in data["results"] for f in r["findings"] if f["status"] == "gap")
    used = {f["rule_id"] for r in data["results"] for f in r["findings"]}
    assert used == set(data["rules"])
    for rule in data["rules"].values():
        assert rule["basis"] and rule["scanner_reading"]
        assert any(b["weight"] == "law" for b in rule["basis"])
        assert all(b["url"].startswith("https://") and b["pinpoint"] and b["says"] for b in rule["basis"])
    assert data["legal_basis"]["applies_since"] == "2026-08-02"


def test_markdown_and_html_reports(capsys, tmp_path):
    _, md, _ = run(capsys, "media", EX / "media", "--format", "md")
    assert "## Legal basis of these checks" in md and "[Article 50(2), first sentence](https://" in md

    target = tmp_path / "report.html"
    code, out, err = run(capsys, "page", EX / "sites" / "northwind-bad", EX / "sites" / "northwind-good", "-f", "html", "-o", target)
    assert code == 0 and out == "" and "Report written" in err
    html = target.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")
    assert "Legal basis: Article 50(1), first sentence" in html
    assert 'href="https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50"' in html
    assert html.count("<details>") == html.count("</details>") == 4


def test_html_report_escapes_untrusted_text(capsys, tmp_path):
    chat = tmp_path / "x.json"
    chat.write_text(json.dumps([{"role": "assistant", "content": "<script>alert(1)</script> hello"}]))
    _, html, _ = run(capsys, "transcript", chat, "--format", "html")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_rules_command(capsys):
    code, out, _ = run(capsys, "rules")
    assert code == 0 and "INT-001" in out and "Scanner's reading" in out
    _, out, _ = run(capsys, "rules", "--format", "json")
    assert len(json.loads(out)) == len(rules.all_rules())


def test_every_rule_has_a_checkable_basis():
    for rule in rules.all_rules():
        assert rule.basis, rule.id
        law = [b for b in rule.basis if rules.SOURCES[b.source].weight == "law"]
        assert law, f"{rule.id} has no basis in the Act itself"
        for basis in law:
            assert re.match(r"Article 50\(\d\), ", basis.pinpoint), basis.pinpoint
        # the paragraphs named in the rule header are exactly the ones its law basis points at
        named = set(re.findall(r"50\(\d\)", rule.paragraph))
        cited = {re.match(r"Article (50\(\d\))", b.pinpoint).group(1) for b in law}
        assert named == cited, f"{rule.id}: header says {named}, basis cites {cited}"
        assert rule.reading


def test_mapping_document_is_generated_from_the_catalogue():
    doc = (ROOT / "docs" / "article-50-mapping.md").read_text(encoding="utf-8")
    assert doc.strip() == rules.to_markdown().strip(), "run: ai-disclosure-scan rules --format md > docs/article-50-mapping.md"


@pytest.mark.parametrize("fmt", ["text", "json", "md", "html"])
def test_every_format_renders_errors_without_crashing(capsys, fmt, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops")
    good = EX / "transcripts" / "01-discloses-up-front.json"
    code, out, _ = run(capsys, "transcript", bad, good, "--format", fmt)
    assert code == 0 and "bad.json" in out
