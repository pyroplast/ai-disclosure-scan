"""Browser mode: render the page, open the chat widget, read what it says first.

A static scan cannot see inside a chat widget. This module drives a real
browser (Chromium through Playwright) to:

1. load the page and let its scripts run;
2. record all visible text, including text inside iframes and shadow DOM;
3. open the widget, first through the vendor's own JavaScript API and, if
   that fails, by clicking something that looks like a chat launcher;
4. record the text again and keep what is new: the widget's greeting and UI.

Playwright is optional:

    pip install "ai-disclosure-scan[browser]"
    playwright install chromium        # or have Google Chrome installed
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import lexicon

INSTALL_HINT = (
    "browser mode needs Playwright: pip install 'ai-disclosure-scan[browser]' "
    "and then 'playwright install chromium' (or install Google Chrome)"
)

# Vendor JavaScript that opens the widget. Each entry is tried in the page;
# it must return true when the call was made.
OPENERS: dict[str, str] = {
    "Intercom": "() => { if (typeof window.Intercom === 'function') { window.Intercom('show'); return true } return false }",
    "Zendesk": "() => { if (typeof window.zE === 'function') { try { window.zE('messenger', 'open') } catch (e) { window.zE('webWidget', 'open') } return true } return false }",
    "Drift": "() => { if (window.drift && window.drift.api) { window.drift.api.openChat(); return true } return false }",
    "Tidio": "() => { if (window.tidioChatApi) { window.tidioChatApi.open(); return true } return false }",
    "Crisp": "() => { if (window.$crisp && window.$crisp.push) { window.$crisp.push(['do', 'chat:open']); return true } return false }",
    "HubSpot": "() => { const w = window.HubSpotConversations && window.HubSpotConversations.widget; if (w) { w.open(); return true } return false }",
    "Freshchat": "() => { if (window.fcWidget) { window.fcWidget.open(); return true } return false }",
    "LiveChat": "() => { if (window.LiveChatWidget) { window.LiveChatWidget.call('maximize'); return true } return false }",
    "Tawk.to": "() => { if (window.Tawk_API && window.Tawk_API.maximize) { window.Tawk_API.maximize(); return true } return false }",
    "Gorgias": "() => { if (window.GorgiasChat && window.GorgiasChat.open) { window.GorgiasChat.open(); return true } return false }",
    "Olark": "() => { if (typeof window.olark === 'function') { window.olark('api.box.expand'); return true } return false }",
    "Smartsupp": "() => { if (typeof window.smartsupp === 'function') { window.smartsupp('chat:open'); return true } return false }",
    "Chatwoot": "() => { if (window.$chatwoot) { window.$chatwoot.toggle('open'); return true } return false }",
    "Botpress": "() => { const b = window.botpress || window.botpressWebChat; if (b && b.open) { b.open(); return true } if (b && b.sendEvent) { b.sendEvent({ type: 'show' }); return true } return false }",
    "Voiceflow": "() => { const c = window.voiceflow && window.voiceflow.chat; if (c && c.open) { c.open(); return true } return false }",
    "Landbot": "() => { const l = window.myLandbot || window.landbot; if (l && l.open) { l.open(); return true } return false }",
    "Kommunicate": "() => { if (window.KommunicateGlobal && window.KommunicateGlobal.openChat) { window.KommunicateGlobal.openChat(); return true } return false }",
    "Chatbase": "() => { if (window.chatbase && typeof window.chatbase === 'function') { window.chatbase('open'); return true } return false }",
    "Userlike": "() => { if (window.userlike && window.userlike.userlikeStartChat) { window.userlike.userlikeStartChat(); return true } return false }",
}

# How many openers to try before giving up on a page.
MAX_ATTEMPTS = 4

# Things a launcher usually looks like. Tried in order, in every frame.
LAUNCHER_SELECTORS = [
    "[aria-label*='chat' i]",
    "[aria-label*='message' i]",
    "[aria-label*='assistant' i]",
    "[aria-label*='support' i]",
    "[aria-label*='help' i]",
    "[aria-label*='ayuda' i]",
    "[title*='chat' i]",
    "[id*='launcher' i]",
    "[class*='launcher' i]",
    "[class*='chat-button' i]",
    "[class*='chat-bubble' i]",
    "[class*='chatbot' i]",
    "[data-testid*='launcher' i]",
]

# Walks the DOM, including open shadow roots, and returns visible text.
_TEXT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const visible = (el) => {
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const walk = (root) => {
    const it = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let node = it.currentNode;
    while (node) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const tag = node.tagName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') {
          node = it.nextSibling() || nextUp(it);
          continue;
        }
        if (node.shadowRoot) walk(node.shadowRoot);
      } else if (node.nodeType === Node.TEXT_NODE) {
        const t = node.textContent.replace(/\s+/g, ' ').trim();
        const parent = node.parentElement;
        if (t && parent && visible(parent) && !seen.has(t)) { seen.add(t); out.push(t); }
      }
      node = it.nextNode();
    }
  };
  const nextUp = (it) => { while (it.parentNode()) { const s = it.nextSibling(); if (s) return s; } return null; };
  walk(document.body || document.documentElement);
  return out;
}
"""

_SCRIPTS_JS = r"""
() => {
  const urls = Array.from(document.querySelectorAll('script[src], iframe[src]')).map(e => e.src);
  const tags = new Set();
  const all = (root) => root.querySelectorAll('*').forEach(e => { if (e.tagName.includes('-')) tags.add(e.tagName.toLowerCase()); if (e.shadowRoot) all(e.shadowRoot); });
  all(document);
  return { urls, tags: Array.from(tags) };
}
"""


@dataclass
class Capture:
    url: str
    final_url: str = ""
    html: str = ""
    vendors: list[str] = field(default_factory=list)
    vendor_kinds: list[str] = field(default_factory=list)
    opened: bool = False
    open_method: str = ""
    before: list[str] = field(default_factory=list)
    after: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def widget_text(self) -> str:
        """Text that appeared after opening the widget."""
        before = set(self.before)
        return "\n".join(line for line in self.after if line not in before)

    def to_dict(self) -> dict[str, object]:
        return {
            "final_url": self.final_url,
            "widgets_at_runtime": self.vendors,
            "widget_opened": self.opened,
            "open_method": self.open_method,
            "widget_text": self.widget_text[:2000],
        }


def available() -> tuple[bool, str]:
    try:
        from playwright import sync_api

        del sync_api
    except ImportError:
        return False, INSTALL_HINT
    return True, ""


def capture(url: str, timeout: float = 30.0, settle: float = 4.0, wait_after_open: float = 5.0) -> Capture:
    """Load a page in a headless browser, open its chat widget and record what it shows."""
    result = Capture(url)
    ok, hint = available()
    if not ok:
        result.error = hint
        return result

    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            browser = _launch(pw)
        except PlaywrightError as exc:
            result.error = f"could not start a browser ({_first_line(exc)}). {INSTALL_HINT}"
            return result
        try:
            context = browser.new_context(
                user_agent=_user_agent(browser.version),
                locale="en-GB",
                viewport={"width": 1366, "height": 900},
            )
            page = context.new_page()
            page.set_default_timeout(timeout * 1000)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            _settle(page, settle)
            result.final_url = page.url
            result.html = page.content()
            result.before = _all_text(page)

            vendors = _runtime_vendors(page)
            result.vendors = [v.name for v in vendors]
            result.vendor_kinds = [v.kind for v in vendors]

            tried: list[str] = []
            for method, action in _open_attempts(page, vendors):
                try:
                    if not action():
                        continue
                except Exception:  # noqa: BLE001 - a failed opener is just one attempt
                    continue
                page.wait_for_timeout(wait_after_open * 1000)
                result.after = _all_text(page)
                if result.widget_text.strip():
                    result.opened = True
                    result.open_method = method
                    break
                tried.append(method)
                if len(tried) >= MAX_ATTEMPTS:
                    break
            if not result.opened and tried:
                result.open_method = "; ".join(tried) + " (nothing new appeared)"
        except PlaywrightError as exc:
            result.error = f"browser error: {_first_line(exc)}"
        finally:
            browser.close()
    return result


def _launch(pw):
    from playwright.sync_api import Error as PlaywrightError

    try:
        return pw.chromium.launch(headless=True)
    except PlaywrightError:
        return pw.chromium.launch(headless=True, channel="chrome")


def _user_agent(version: str) -> str:
    from . import __version__

    return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{version} Safari/537.36 ai-disclosure-scan/{__version__}"
    )


def _settle(page, seconds: float) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=seconds * 1000)
    except Exception:  # noqa: BLE001 - busy pages never go idle; that is fine
        pass
    page.wait_for_timeout(min(seconds, 2.0) * 1000)


def _all_text(page) -> list[str]:
    lines: list[str] = []
    for frame in page.frames:
        try:
            lines.extend(frame.evaluate(_TEXT_JS))
        except Exception:  # noqa: BLE001 - detached or cross-process frames
            continue
    return lines


def _runtime_vendors(page) -> list[lexicon.Vendor]:
    urls: list[str] = []
    tags: set[str] = set()
    for frame in page.frames:
        urls.append(frame.url)
        try:
            found = frame.evaluate(_SCRIPTS_JS)
        except Exception:  # noqa: BLE001
            continue
        urls.extend(found["urls"])
        tags.update(found["tags"])
    return lexicon.detect_vendors("\n".join(urls), tags)


def _open_attempts(page, vendors: list[lexicon.Vendor]):
    """Ways to open the widget, best first: vendor APIs, then launcher-looking elements."""
    for vendor in vendors:
        script = OPENERS.get(vendor.name)
        if script:
            yield f"{vendor.name} JavaScript API", lambda script=script: bool(page.evaluate(script))
    frames = sorted(page.frames, key=lambda f: f == page.main_frame)  # widget frames first
    for selector in LAUNCHER_SELECTORS:
        for frame in frames:
            try:
                locator = frame.locator(selector)
                count = min(locator.count(), 5)
            except Exception:  # noqa: BLE001 - detached frame
                continue
            for i in range(count):
                item = locator.nth(i)
                try:
                    visible = item.is_visible()
                except Exception:  # noqa: BLE001
                    continue
                if visible:
                    yield f"clicked {selector}", lambda item=item: (item.click(timeout=3000), True)[1]
                    break


def _first_line(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:200] if str(exc).strip() else exc.__class__.__name__


def pause(seconds: float) -> None:
    time.sleep(seconds)
