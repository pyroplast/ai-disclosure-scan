"""Web page checks.

A page scan reads the HTML a server sends (or a local .html file) and looks for:

* chat and voice widgets, and whether the page tells visitors an AI is involved
  (Article 50(1) and 50(5));
* media on the page that is AI-made, and whether the page labels it
  (Article 50(4) and 50(5)).

It is a static scan: it does not run JavaScript and cannot open the widget.
Findings about chat are therefore signals to review, not verdicts.
"""

from __future__ import annotations

import base64
import re
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from . import __version__, lexicon, media
from .models import Status, TargetResult

USER_AGENT = f"ai-disclosure-scan/{__version__} (+https://github.com/pyroplast/ai-disclosure-scan)"
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_MEDIA_BYTES = 8 * 1024 * 1024

_VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr",
}  # fmt: skip
_NO_TEXT = {"script", "style", "template"}
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.IGNORECASE)
_HIDDEN_CLASSES = {"sr-only", "visually-hidden", "screen-reader-text", "hidden", "d-none", "invisible"}
_ATTR_TEXT = ("alt", "title", "aria-label", "placeholder")
_AI_META_NAMES = {"ai-generated", "ai-content", "ai_generated", "generated-by-ai", "ai-disclosure"}


class FetchError(Exception):
    pass


@dataclass
class Page:
    """What the parser pulled out of one HTML document."""

    visible: list[str] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)  # hidden elements, noscript, attribute text, meta
    script_urls: list[str] = field(default_factory=list)
    inline_scripts: list[str] = field(default_factory=list)
    iframe_urls: list[str] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    images: list[str] = field(default_factory=list)
    av_sources: list[str] = field(default_factory=list)
    ai_declarations: list[str] = field(default_factory=list)  # machine-readable "this is AI" markers
    title: str = ""

    @property
    def visible_text(self) -> str:
        return " ".join(" ".join(self.visible).split())

    @property
    def hidden_text(self) -> str:
        return " ".join(" ".join(self.hidden).split())

    @property
    def script_text(self) -> str:
        return "\n".join(self.inline_scripts)


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page = Page()
        self._stack: list[tuple[str, bool]] = []  # (tag, hides its content)
        self._raw: str = ""  # script/style/title currently open
        self._script_is_jsonld = False

    # -- helpers ------------------------------------------------------------
    def _hidden(self) -> bool:
        return any(hides for _, hides in self._stack)

    @staticmethod
    def _hides(tag: str, attrs: dict[str, str]) -> bool:
        if tag == "noscript" or "hidden" in attrs:
            return True
        if attrs.get("aria-hidden", "").lower() == "true":
            return True
        if _HIDDEN_STYLE.search(attrs.get("style", "")):
            return True
        return any(token in _HIDDEN_CLASSES for token in attrs.get("class", "").lower().split())

    # -- parser callbacks ---------------------------------------------------
    def handle_starttag(self, tag: str, attr_list: list[tuple[str, str | None]]) -> None:
        attrs = {k.lower(): (v or "") for k, v in attr_list}
        page = self.page
        page.tags.add(tag)

        for name in _ATTR_TEXT:
            if attrs.get(name):
                page.hidden.append(attrs[name])
        for name, value in attrs.items():
            if name.startswith("data-ai") and value.lower() not in {"", "false", "0", "no"}:
                page.ai_declarations.append(f'{name}="{value}"')

        if tag == "script":
            if attrs.get("src"):
                page.script_urls.append(attrs["src"])
            self._script_is_jsonld = "ld+json" in attrs.get("type", "").lower()
            self._raw = "script"
        elif tag in ("style", "title"):
            self._raw = tag
        elif tag == "iframe" and attrs.get("src"):
            page.iframe_urls.append(attrs["src"])
        elif tag == "img" and attrs.get("src"):
            page.images.append(attrs["src"])
        elif tag in ("video", "audio", "source") and attrs.get("src"):
            page.av_sources.append(attrs["src"])
        elif tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            content = attrs.get("content", "")
            if name in _AI_META_NAMES and content.lower() not in {"", "false", "0", "no", "none"}:
                page.ai_declarations.append(f'<meta name="{name}" content="{content}">')
            elif name in {"description", "og:description", "og:title", "twitter:description"} and content:
                page.hidden.append(content)

        if tag not in _VOID:
            self._stack.append((tag, self._hides(tag, attrs)))

    def handle_startendtag(self, tag: str, attr_list: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attr_list)
        if tag not in _VOID and self._stack and self._stack[-1][0] == tag:
            self._stack.pop()
            self._raw = ""

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "title"):
            self._raw = ""
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        page = self.page
        if self._raw == "script":
            if self._script_is_jsonld:
                if re.search(r"digitalSourceType", data) and re.search(r"TrainedAlgorithmicMedia", data, re.IGNORECASE):
                    page.ai_declarations.append("JSON-LD digitalSourceType: trained algorithmic media")
            else:
                page.inline_scripts.append(data)
            return
        if self._raw == "style":
            return
        if self._raw == "title":
            page.title = (page.title + " " + data).strip()
            return
        if any(tag in _NO_TEXT for tag, _ in self._stack):
            return
        (page.hidden if self._hidden() else page.visible).append(data)


def parse_html(html: str) -> Page:
    parser = _Parser()
    parser.feed(html)
    parser.close()
    return parser.page


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


class Fetcher:
    """Small HTTP client: one user agent, size caps, optional robots.txt check."""

    def __init__(self, timeout: float = 15.0, respect_robots: bool = True) -> None:
        self.timeout = timeout
        self.respect_robots = respect_robots
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def get(self, url: str, max_bytes: int) -> tuple[bytes, str, str]:
        """Return (body, final_url, content_type)."""
        if self.respect_robots and not self.allowed(url):
            raise FetchError("blocked by the site's robots.txt (use --ignore-robots to override)")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(max_bytes + 1)[:max_bytes]
                return body, response.geturl(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise FetchError(f"HTTP {exc.code} {exc.reason}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            reason = getattr(exc, "reason", exc)
            raise FetchError(f"could not fetch: {reason}") from exc

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)

    def _load_robots(self, origin: str) -> urllib.robotparser.RobotFileParser | None:
        request = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read(512 * 1024).decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, ValueError):
            return None  # no robots.txt, or unreachable: nothing forbids the fetch
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(text.splitlines())
        return parser


def _decode(body: bytes, content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    if not match:
        match = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.IGNORECASE)
        charset = match.group(1).decode("ascii") if match else "utf-8"
    else:
        charset = match.group(1)
    try:
        return body.decode(charset, "replace")
    except LookupError:
        return body.decode("utf-8", "replace")


def is_url(target: str) -> bool:
    return target.lower().startswith(("http://", "https://"))


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------


def scan(
    target: str,
    fetcher: Fetcher | None = None,
    check_media: bool = True,
    max_media: int = 12,
    use_browser: bool = False,
    browser_timeout: float = 30.0,
    accept_cookies: bool = False,
    follow_contact: bool = False,
) -> TargetResult:
    result = TargetResult(target, "page")
    fetcher = fetcher or Fetcher()

    if use_browser:
        return _scan_in_browser(
            target, result, fetcher, check_media, max_media, browser_timeout, accept_cookies, follow_contact
        )

    base_url = ""
    base_dir: Path | None = None
    try:
        if is_url(target):
            body, base_url, content_type = fetcher.get(target, MAX_HTML_BYTES)
            html = _decode(body, content_type)
        else:
            path = Path(target)
            if path.is_dir():
                path = path / "index.html"
            html = _decode(path.read_bytes()[:MAX_HTML_BYTES], "")
            base_dir = path.parent
    except (FetchError, OSError) as exc:
        result.error = str(exc)
        return result

    page = parse_html(html)
    _check_chat(page, result)
    _check_labels(page, result, fetcher, base_url, base_dir, check_media, max_media)
    return result


def _check_chat(page: Page, result: TargetResult) -> None:
    haystack = "\n".join(page.script_urls + page.iframe_urls + [page.script_text])
    vendors = lexicon.detect_vendors(haystack, page.tags)
    result.facts["widgets"] = [{"name": v.name, "kind": v.kind} for v in vendors]

    if not vendors:
        result.add("PAGE-005", Status.INFO, "No known chat or voice widget signature in the page HTML.")
        return

    names = ", ".join(v.name for v in vendors)
    kinds = {v.kind for v in vendors}
    if "voice" in kinds:
        surface = "voice agent"
    elif "ai" in kinds:
        surface = "AI chat product"
    else:
        surface = "live-chat platform that can run AI agents"
    found = f"Widget found: {names} ({surface})."

    visible = page.visible_text
    notice = lexicon.find_chat_notice(visible)
    if notice:
        result.add(
            "PAGE-003", Status.PASS, f"{found} The page shows a clear AI notice.", lexicon.snippet(visible, notice[0])
        )
        return

    config_notice = lexicon.find_chat_notice(page.script_text)
    if config_notice:
        result.add(
            "PAGE-003",
            Status.PASS,
            f"{found} The widget's configuration contains an AI notice. Confirm it is what visitors see first.",
            lexicon.snippet(page.script_text, config_notice[0]),
            "widget configuration",
        )
        return

    mention = lexicon.find_explicit(visible)
    if mention:
        result.add(
            "PAGE-002",
            Status.REVIEW,
            f"{found} AI is mentioned in the page text, but not as a notice tied to the chat.",
            lexicon.snippet(visible, mention[0]),
        )
        return

    hidden = page.hidden_text
    hidden_hit = lexicon.find_chat_notice(hidden) or lexicon.find_explicit(hidden)
    if hidden_hit:
        result.add(
            "PAGE-004",
            Status.REVIEW,
            f"{found} AI wording appears only in hidden elements, attributes or metadata.",
            lexicon.snippet(hidden, hidden_hit[0]),
        )
        return

    spoken = " For a voice agent the notice has to be spoken or shown before the conversation starts." if "voice" in kinds else ""
    result.add(
        "PAGE-001",
        Status.REVIEW,
        f"{found} Nothing in the page HTML tells visitors an AI is involved.{spoken}",
    )


def _check_labels(
    page: Page,
    result: TargetResult,
    fetcher: Fetcher,
    base_url: str,
    base_dir: Path | None,
    check_media: bool,
    max_media: int,
) -> None:
    visible = page.visible_text
    label = lexicon.find_ai_label(visible)

    ai_media: list[str] = []
    inspected = 0
    skipped = 0
    if check_media:
        sources = list(dict.fromkeys(page.images + page.av_sources))
        for src in sources:
            if inspected >= max_media:
                skipped = len(sources) - inspected
                break
            data = _load_media(src, fetcher, base_url, base_dir)
            if data is None:
                continue
            inspected += 1
            facts = media.inspect(data)
            if facts.ai_evident:
                how = (
                    "marked as AI-made" if facts.marked_ai else "generator traces: " + ", ".join(facts.generator_hints)
                )
                ai_media.append(f"{_short(src)} ({how})")
    result.facts["media_inspected"] = inspected
    result.facts["media_not_inspected"] = skipped
    result.facts["ai_media"] = ai_media

    if ai_media:
        listing = "; ".join(ai_media[:5]) + ("; …" if len(ai_media) > 5 else "")
        if label:
            result.add(
                "LBL-002",
                Status.PASS,
                f"{len(ai_media)} AI-made media file(s) on the page, and the page carries a visible AI label.",
                f"Label found: “{label[0].text}”. Media: {listing}",
            )
        else:
            result.add(
                "LBL-001",
                Status.REVIEW,
                f"{len(ai_media)} AI-made media file(s) on the page and no visible AI label in the page text.",
                listing,
            )

    if page.ai_declarations and not label:
        result.add(
            "LBL-003",
            Status.REVIEW,
            "The page's code declares AI-generated content, but the visible text carries no AI label.",
            "; ".join(page.ai_declarations[:3]),
        )


def _load_media(src: str, fetcher: Fetcher, base_url: str, base_dir: Path | None) -> bytes | None:
    src = src.strip()
    if src.startswith("data:"):
        head, _, payload = src.partition(",")
        if ";base64" not in head:
            return None
        try:
            return base64.b64decode(payload, validate=False)[:MAX_MEDIA_BYTES]
        except ValueError:
            return None
    if base_url:
        url = urllib.parse.urljoin(base_url, src)
    elif is_url(src):
        url = src
    elif src.startswith("//"):
        url = "https:" + src
    else:
        if base_dir is None:
            return None
        local = (base_dir / urllib.parse.unquote(src.split("?")[0].split("#")[0])).resolve()
        try:
            return local.read_bytes()[:MAX_MEDIA_BYTES]
        except OSError:
            return None
    if not is_url(url):
        return None
    try:
        body, _, _ = fetcher.get(url, MAX_MEDIA_BYTES)
        return body
    except FetchError:
        return None


def _short(src: str) -> str:
    if src.startswith("data:"):
        return "inline data: image"
    name = src.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return name or src[:60]


# ---------------------------------------------------------------------------
# Browser mode
# ---------------------------------------------------------------------------

_STATIC_CHAT_RULES = {"PAGE-001", "PAGE-002", "PAGE-003", "PAGE-004"}


def _scan_in_browser(
    target: str,
    result: TargetResult,
    fetcher: Fetcher,
    check_media: bool,
    max_media: int,
    timeout: float,
    accept_cookies: bool = False,
    follow_contact: bool = False,
) -> TargetResult:
    from . import browser

    if target.lower().startswith("file://"):
        url = target
        target = urllib.request.url2pathname(urllib.parse.urlsplit(target).path)
    else:
        url = target if is_url(target) else Path(target).resolve().as_uri()
    if is_url(target) and fetcher.respect_robots and not fetcher.allowed(target):
        result.error = "blocked by the site's robots.txt (use --ignore-robots to override)"
        return result

    cap = browser.capture(url, timeout=timeout, accept_cookies=accept_cookies, follow_contact=follow_contact)
    if cap.error and not cap.html:
        result.error = cap.error
        return result

    # The rendered DOM replaces the server's HTML, so notices drawn by JavaScript count.
    page = parse_html(cap.html)
    base_url = cap.final_url if is_url(cap.final_url) else ""
    if cap.final_url.startswith("file://"):
        local = Path(urllib.request.url2pathname(urllib.parse.urlsplit(cap.final_url).path))
        target = str(local)
    base_dir = None if base_url else Path(target if not Path(target).is_dir() else Path(target) / "index.html").parent
    _check_chat(page, result)
    _check_labels(page, result, fetcher, base_url, base_dir, check_media, max_media)
    result.facts["browser"] = cap.to_dict()
    if cap.error:
        result.facts["browser"]["error"] = cap.error

    if not cap.vendors and not result.facts.get("widgets") and not cap.opened:
        return result  # no widget: PAGE-005 already says so

    if not cap.opened:
        method = cap.open_method or "no launcher found"
        result.add("BRW-004", Status.REVIEW, f"The widget could not be opened ({method}).")
        return result

    # The widget was opened: what it showed supersedes the static guesses about it.
    result.findings = [f for f in result.findings if f.rule_id not in _STATIC_CHAT_RULES]
    text = cap.widget_text
    where = f"widget opened via {cap.open_method}"
    claims = lexicon.find_human_claims(text)
    explicit = lexicon.find_explicit(text)
    weak = lexicon.find_weak(text)
    persona = lexicon.find_persona_name(text)
    if persona:
        result.facts["persona_name"] = persona

    if claims:
        result.add("BRW-003", Status.GAP, "The widget's opening text claims to be a person.", lexicon.snippet(text, claims[0]), where)
    if explicit:
        result.add("BRW-010", Status.PASS, "The widget's opening text says an AI is involved.", lexicon.snippet(text, explicit[0]), where)
    elif claims:
        pass  # BRW-003 already says what matters
    elif weak:
        result.add("BRW-002", Status.REVIEW, "The widget uses a generic label and never says AI.", lexicon.snippet(text, weak[0]), where)
    else:
        kinds = set(cap.vendor_kinds) | {w["kind"] for w in result.facts.get("widgets", [])}
        ai_product = bool(kinds & {"ai", "voice"})
        who = f" It introduces itself as “{persona}”." if persona else ""
        result.add(
            "BRW-001",
            Status.GAP if ai_product else Status.REVIEW,
            "None of the text the widget showed says an AI is involved." + who
            + ("" if ai_product else " The platform also supports human agents, so a person has to confirm an AI answers."),
            text[:240],
            where,
        )
    return result
