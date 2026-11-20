"""Where a page scan actually looked, compared with what was asked for.

The scanner always requests the exact URL it was given (scheme, host, path and
query). Redirects, and the opt-in contact-page fallback, can still put the
analysis on a different page. Nothing here repairs that silently: every
difference that matters becomes a finding the reader can see.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass

from .models import Status, TargetResult

# Hosts whose /<owner>/<repo> pages show source code, not the product itself.
CODE_HOSTS = {"github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "sourceforge.net", "gitee.com"}

_LOGIN_PATH = re.compile(
    r"(^|/)(login|log-in|signin|sign-in|sign_in|signup|auth|sso|oauth|session|sessions|account/login|"
    r"users/sign_in|iniciar-sesion|acceso|identificacion|anmelden|connexion)(/|$|\.|\?)",
    re.IGNORECASE,
)

MATERIAL = "material"
MINOR = "minor"


@dataclass(frozen=True)
class Drift:
    level: str  # MATERIAL or MINOR
    reason: str


def _host(netloc: str) -> str:
    host = netloc.lower().rsplit("@", 1)[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _path(path: str) -> str:
    return path.rstrip("/") or "/"


def classify_drift(requested: str, final: str) -> Drift | None:
    """Compare the URL that was asked for with the URL that was analysed.

    Ignored: http to https, adding or dropping "www.", a trailing slash, a
    fragment, and port 80/443 spelled out. Anything else is reported.
    """
    if not requested or not final or requested == final:
        return None
    a = urllib.parse.urlsplit(requested)
    b = urllib.parse.urlsplit(final)
    if a.scheme not in ("http", "https") or b.scheme not in ("http", "https"):
        return None
    if _host(a.netloc) != _host(b.netloc):
        return Drift(MATERIAL, f"a different host ({_host(b.netloc)})")
    if _LOGIN_PATH.search(b.path) and not _LOGIN_PATH.search(a.path):
        return Drift(MATERIAL, "a sign-in page")
    if _path(a.path) != "/" and _path(b.path) == "/":
        return Drift(MATERIAL, "the site's root page")
    if _path(a.path) != _path(b.path):
        return Drift(MINOR, "a different path")
    if a.query and a.query != b.query:
        return Drift(MINOR, "the same path with a different query string")
    return None


def code_repository(url: str) -> str:
    """Return "owner/repo" when the URL is a repository page on a code host, else ""."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or _host(parts.netloc) not in CODE_HOSTS:
        return ""
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        return ""
    return f"{segments[0]}/{segments[1]}"


def annotate(result: TargetResult, requested: str, final: str, analysed: str = "") -> None:
    """Record the URLs on the result and add a note for every mismatch that matters.

    Call this after the checks ran, so the notes can point every other finding
    at the page it actually describes.
    """
    analysed = analysed or final
    result.requested_url = requested
    result.final_url = final
    result.analysed_url = analysed

    repo = code_repository(requested)
    if repo:
        result.add(
            "TGT-004",
            Status.INFO,
            f"This is the code-host page of the repository {repo}. The web scan checks the live interface a "
            "visitor sees at this exact URL, not the repository's source files, so the findings describe this "
            "page, not the software in the repository.",
            requested,
        )

    drift = classify_drift(requested, final)
    if drift is not None:
        status = Status.REVIEW if drift.level == MATERIAL else Status.INFO
        result.add(
            "TGT-001" if drift.level == MATERIAL else "TGT-002",
            status,
            f"The requested URL redirected to {drift.reason}. The findings describe the page it landed on, "
            "which may not be the page you meant to check.",
            f"requested {requested} → landed on {final}",
        )

    if analysed != final:
        result.add(
            "TGT-003",
            Status.INFO,
            "No chat widget was found on the requested page, so the contact-page fallback (--follow-contact) "
            "analysed the site's contact or help page instead. The page findings describe that page.",
            f"landed on {final} → analysed {analysed}",
        )

    moved = analysed if analysed != requested and (drift is not None or analysed != final) else ""
    if moved:
        for finding in result.findings:
            if finding.rule_id.startswith("TGT-"):
                continue
            note = f"evaluated on {moved}"
            finding.location = f"{finding.location}; {note}" if finding.location else note
