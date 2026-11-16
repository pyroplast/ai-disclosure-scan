"""Data shapes shared by every check and every report format."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    """What a finding means for the reader.

    GAP     a concrete signal that an Article 50 duty is probably not met
    REVIEW  a person has to look; the scanner cannot decide on its own
    PASS    the signal the duty calls for was found
    INFO    context, or something this scanner cannot assess
    """

    GAP = "gap"
    REVIEW = "review"
    PASS = "pass"
    INFO = "info"


STATUS_ORDER = [Status.GAP, Status.REVIEW, Status.PASS, Status.INFO]


@dataclass
class Finding:
    rule_id: str
    status: Status
    detail: str
    evidence: str = ""
    location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": self.evidence,
            "location": self.location,
        }


@dataclass
class TargetResult:
    """Everything found for one scanned thing: a page, a conversation or a file."""

    target: str
    kind: str  # "page" | "transcript" | "media"
    findings: list[Finding] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def add(self, rule_id: str, status: Status, detail: str, evidence: str = "", location: str = "") -> None:
        self.findings.append(Finding(rule_id, status, detail, _clip(evidence), location))

    def worst(self) -> Status | None:
        for status in STATUS_ORDER:
            if any(f.status is status for f in self.findings):
                return status
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "kind": self.kind,
            "error": self.error,
            "facts": self.facts,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class Report:
    tool_version: str
    generated_at: str
    results: list[TargetResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in STATUS_ORDER}
        for result in self.results:
            for finding in result.findings:
                out[finding.status.value] += 1
        return out

    def errors(self) -> int:
        return sum(1 for r in self.results if r.error)

    def all_findings(self) -> list[tuple[TargetResult, Finding]]:
        return [(r, f) for r in self.results for f in r.findings]


def _clip(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
