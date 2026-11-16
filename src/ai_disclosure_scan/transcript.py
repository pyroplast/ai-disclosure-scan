"""Conversation checks: does the assistant tell people it is an AI, and when?

Covers Article 50(1) (people must be informed they are interacting with an AI
system) and the timing rule in Article 50(5) (at the latest at the time of the
first interaction).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import lexicon
from .models import Status, TargetResult

USER_ROLES = {
    "user", "human", "customer", "visitor", "client", "guest", "me", "you", "caller", "end_user", "enduser",
    "contact", "usuario", "cliente", "kunde", "kundin", "utilisateur", "utente", "klant", "klient",
}  # fmt: skip
ASSISTANT_ROLES = {
    "assistant", "ai", "bot", "agent", "model", "chatbot", "support", "operator", "gpt", "virtual_agent",
    "rep", "asistente", "agente", "assistent", "assistente",
}  # fmt: skip
SKIP_ROLES = {"system", "developer", "tool", "function", "tool_result", "note", "internal", "event"}

TRANSCRIPT_SUFFIXES = {".json", ".jsonl", ".ndjson", ".txt", ".md", ".log"}

_ROLE_KEYS = ("role", "speaker", "author", "from", "sender")
_TEXT_KEYS = ("content", "text", "message", "value", "body")
_LIST_KEYS = ("messages", "turns", "transcript", "conversation", "dialogue")


@dataclass
class Message:
    role: str  # "user" | "assistant"
    text: str
    speaker: str = ""  # the label as written in the source


@dataclass
class Conversation:
    id: str
    messages: list[Message] = field(default_factory=list)
    roles_guessed: bool = False


class TranscriptError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load(path: Path) -> list[Conversation]:
    """Read one file and return every conversation in it."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    return load_text(raw, path.suffix.lower())


def load_text(raw: str, suffix: str = "") -> list[Conversation]:
    """Parse conversations from a string: JSON, JSONL or a plain-text chat log."""
    raw = raw.lstrip("﻿")
    if not suffix:
        lines = [line for line in raw.strip().splitlines() if line.strip()]
        if len(lines) > 1 and all(line.lstrip().startswith("{") for line in lines):
            suffix = ".jsonl"
    if suffix in {".jsonl", ".ndjson"}:
        return _from_jsonl(raw)
    if suffix == ".json" or raw.lstrip()[:1] in {"[", "{"}:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            if suffix == ".json":
                raise TranscriptError(f"not valid JSON: {exc}") from exc
            return _from_text(raw)
        return _from_obj(obj)
    return _from_text(raw)


def _from_jsonl(raw: str) -> list[Conversation]:
    rows: list[Any] = []
    for n, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise TranscriptError(f"line {n} is not valid JSON: {exc}") from exc
    if not rows:
        return []
    if all(_is_message(row) for row in rows):
        return [_conversation("1", rows)]
    out: list[Conversation] = []
    for n, row in enumerate(rows, 1):
        out.extend(_from_obj(row, default_id=str(n)))
    return out


def _from_obj(obj: Any, default_id: str = "1") -> list[Conversation]:
    if isinstance(obj, dict):
        if isinstance(obj.get("conversations"), list):
            out: list[Conversation] = []
            for n, item in enumerate(obj["conversations"], 1):
                out.extend(_from_obj(item, default_id=str(n)))
            return out
        for key in _LIST_KEYS:
            if isinstance(obj.get(key), list):
                conv_id = str(obj.get("id") or obj.get("conversation_id") or obj.get("session_id") or default_id)
                return [_conversation(conv_id, obj[key])]
        raise TranscriptError("JSON object has no 'messages', 'turns', 'transcript' or 'conversations' list")
    if isinstance(obj, list):
        if not obj:
            return []
        if all(_is_message(item) for item in obj):
            return [_conversation(default_id, obj)]
        out = []
        for n, item in enumerate(obj, 1):
            out.extend(_from_obj(item, default_id=str(n)))
        return out
    raise TranscriptError("unsupported JSON shape: expected a list of messages or an object with 'messages'")


def _is_message(item: Any) -> bool:
    return isinstance(item, dict) and any(k in item for k in _ROLE_KEYS) and any(k in item for k in _TEXT_KEYS)


def _conversation(conv_id: str, items: list[Any]) -> Conversation:
    conv = Conversation(conv_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        label = next((item[k] for k in _ROLE_KEYS if item.get(k)), "")
        if isinstance(label, dict):  # e.g. {"author": {"role": "assistant"}}
            label = label.get("role") or label.get("name") or ""
        label = str(label)
        text = _text_of(next((item[k] for k in _TEXT_KEYS if item.get(k)), ""))
        role = _role_of(label)
        if role is None or not text.strip():
            continue
        if role == "unknown":
            role = "assistant"  # a named speaker in a structured export is the agent persona
        conv.messages.append(Message(role, text.strip(), label))
    return conv


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # content blocks: [{"type": "text", "text": "..."}]
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return ""


def _role_of(label: str) -> str | None:
    key = label.strip().lower().replace(" ", "_").replace("-", "_")
    if key in SKIP_ROLES:
        return None
    if key in USER_ROLES:
        return "user"
    if key in ASSISTANT_ROLES:
        return "assistant"
    return "unknown"


_SPEAKER_LINE = re.compile(
    r"^\s*(?:\[[^\]]{1,40}\]\s*|\(?\d{1,2}:\d{2}(?::\d{2})?\)?\s*[-–]?\s*)?"  # optional timestamp
    r"([A-Za-zÀ-ÿ][\wÀ-ÿ .'’-]{0,30}?)\s*[:：]\s+(.*)$"
)
_SEPARATOR = re.compile(r"^\s*(?:-{3,}|={3,}|\*{3,}|#{1,3}\s*conversation\b.*)\s*$", re.IGNORECASE)


def _from_text(raw: str) -> list[Conversation]:
    lines = raw.splitlines()
    # Pass 1: which labels are really speakers? Known role words always are;
    # other names must open at least two lines ("Sarah: ..."), which keeps
    # "Note: ..." inside a message from being read as a speaker.
    counts: dict[str, int] = {}
    for line in lines:
        match = _SPEAKER_LINE.match(line)
        if match:
            label = match.group(1).strip()
            counts[label] = counts.get(label, 0) + 1
    speakers = {
        label
        for label, n in counts.items()
        if (_role_of(label) in {"user", "assistant", None} and label.lower() != "note")
        or (n >= 2 and len(label.split()) <= 3)
    }

    blocks: list[list[tuple[str, str]]] = [[]]
    for line in lines:
        if _SEPARATOR.match(line):
            if blocks[-1]:
                blocks.append([])
            continue
        match = _SPEAKER_LINE.match(line)
        if match and match.group(1).strip() in speakers:
            blocks[-1].append((match.group(1).strip(), match.group(2).strip()))
        elif blocks[-1] and line.strip():
            label, text = blocks[-1][-1]
            blocks[-1][-1] = (label, (text + "\n" + line.strip()).strip())

    out: list[Conversation] = []
    for n, block in enumerate([b for b in blocks if b], 1):
        conv = Conversation(str(n))
        roles = {label: _role_of(label) for label, _ in block}
        unknown = [label for label, role in roles.items() if role == "unknown"]
        known_user = any(role == "user" for role in roles.values())
        known_assistant = any(role == "assistant" for role in roles.values())
        mapping: dict[str, str | None] = dict(roles)
        if unknown:
            if known_user and not known_assistant:
                for label in unknown:
                    mapping[label] = "assistant"
            elif known_assistant and not known_user:
                for label in unknown:
                    mapping[label] = "user"
            elif known_user and known_assistant:
                for label in unknown:
                    mapping[label] = "assistant"
            else:
                # No role words at all: assume the first speaker is the visitor.
                conv.roles_guessed = True
                first = block[0][0]
                for label in unknown:
                    mapping[label] = "user" if label == first else "assistant"
        for label, text in block:
            role = mapping.get(label)
            if role in {"user", "assistant"} and text:
                conv.messages.append(Message(role, text, label))
        out.append(conv)
    return out


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def analyze(conv: Conversation, target: str, ui_notice: bool = False) -> TargetResult:
    result = TargetResult(target=target, kind="transcript")
    assistant = [(i, m) for i, m in enumerate(conv.messages) if m.role == "assistant"]
    result.facts = {
        "messages": len(conv.messages),
        "assistant_messages": len(assistant),
        "roles_guessed": conv.roles_guessed,
    }
    if not assistant:
        result.error = "no assistant messages found in this conversation"
        return result

    first_index, first = assistant[0]
    persona = lexicon.find_persona_name(first.text) or _speaker_persona(first.speaker)
    if persona:
        result.facts["persona_name"] = persona

    # --- INT-003: human claims, anywhere --------------------------------------
    claim_turns: set[int] = set()
    for index, message in assistant:
        claims = lexicon.find_human_claims(message.text)
        if claims:
            claim_turns.add(index)
            if len(claim_turns) == 1:
                result.add(
                    "INT-003",
                    Status.GAP,
                    "The assistant says it is a person, or denies being a machine.",
                    lexicon.snippet(message.text, claims[0]),
                    _turn(index),
                )

    # --- INT-004: direct question, no clear answer ----------------------------
    questions = 0
    for index, message in enumerate(conv.messages):
        if message.role != "user" or not lexicon.is_identity_question(message.text):
            continue
        questions += 1
        reply = next(((i, m) for i, m in assistant if i > index), None)
        if reply is None:
            continue
        reply_index, reply_message = reply
        if reply_index in claim_turns:
            continue  # already reported as INT-003
        if not lexicon.find_explicit(reply_message.text):
            result.add(
                "INT-004",
                Status.GAP,
                "The user asked what they were talking to and the reply does not say it is an AI.",
                f"User: {message.text} / Assistant: {reply_message.text}",
                _turn(reply_index),
            )
            break
    result.facts["identity_questions"] = questions

    # --- INT-001 / 002 / 005 / 010: disclosure and its timing ------------------
    explicit_first = lexicon.find_explicit(first.text)
    weak_first = lexicon.find_weak(first.text)
    if ui_notice:
        result.add(
            "INT-010",
            Status.INFO,
            "Not checked from the transcript: you declared a visible AI notice in the chat UI (--ui-notice).",
            location=_turn(first_index),
        )
    elif explicit_first:
        result.add(
            "INT-010",
            Status.PASS,
            "The assistant's first message says an AI is involved.",
            lexicon.snippet(first.text, explicit_first[0]),
            _turn(first_index),
        )
    else:
        later = next(((i, m) for i, m in assistant[1:] if lexicon.find_explicit(m.text)), None)
        who = f"introduces itself as “{persona}” and " if persona else ""
        if later is not None:
            later_index, later_message = later
            hit = lexicon.find_explicit(later_message.text)[0]
            result.add(
                "INT-002",
                Status.GAP,
                f"The assistant {who}first says an AI is involved in message {later_index + 1}, "
                f"not in its first message (message {first_index + 1}).",
                lexicon.snippet(later_message.text, hit),
                _turn(later_index),
            )
        elif weak_first:
            result.add(
                "INT-005",
                Status.REVIEW,
                f"The assistant {who}uses a generic label and never says AI in plain words.",
                lexicon.snippet(first.text, weak_first[0]),
                _turn(first_index),
            )
        else:
            result.add(
                "INT-001",
                Status.GAP,
                f"The assistant {who}never says an AI is involved.",
                first.text,
                _turn(first_index),
            )
    return result


def _turn(index: int) -> str:
    return f"message {index + 1}"


def _speaker_persona(label: str) -> str:
    """A human first name used as the speaker label ("Sarah: Hi!") is a persona too."""
    label = label.strip()
    if not label or _role_of(label) != "unknown":
        return ""
    if re.fullmatch(r"[A-ZÀ-Þ][a-zà-ÿ]{1,15}", label):
        return label
    return ""


# ---------------------------------------------------------------------------
# Entry point used by the CLI
# ---------------------------------------------------------------------------


def scan_path(path: Path, ui_notice: bool = False) -> list[TargetResult]:
    files: list[Path]
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in TRANSCRIPT_SUFFIXES)
        if not files:
            return [TargetResult(str(path), "transcript", error="no transcript files found in this folder")]
    else:
        files = [path]

    results: list[TargetResult] = []
    for file in files:
        try:
            conversations = load(file)
        except (OSError, TranscriptError) as exc:
            results.append(TargetResult(str(file), "transcript", error=str(exc)))
            continue
        if not conversations:
            results.append(TargetResult(str(file), "transcript", error="no conversation found in this file"))
            continue
        many = len(conversations) > 1
        for conv in conversations:
            target = f"{file}#{conv.id}" if many else str(file)
            results.append(analyze(conv, target, ui_notice=ui_notice))
    return results


def scan_text(raw: str, name: str = "transcript", ui_notice: bool = False) -> list[TargetResult]:
    """Scan conversation text handed over directly, for example by an agent."""
    try:
        conversations = load_text(raw)
    except TranscriptError as exc:
        return [TargetResult(name, "transcript", error=str(exc))]
    if not conversations:
        return [TargetResult(name, "transcript", error="no conversation found in the text")]
    many = len(conversations) > 1
    return [analyze(c, f"{name}#{c.id}" if many else name, ui_notice=ui_notice) for c in conversations]
