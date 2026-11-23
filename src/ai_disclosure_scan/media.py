"""Media checks: does a file carry a machine-readable sign that it is AI-made?

Covers the marking side of Article 50(2). The scanner reads container metadata
only; it needs no image library and never decodes pixels or audio.

What it can see
    * C2PA manifests (Content Credentials) in JPEG, PNG, WebP/RIFF, MP4/MOV/HEIF
      and MP3 containers, and whether the manifest declares an AI source type
    * the IPTC Digital Source Type in XMP metadata
    * tool-specific generator traces (Stable Diffusion parameters in PNG text
      chunks, generator names in EXIF/XMP)

What it cannot see
    * invisible watermarks such as SynthID: those need the vendor's detector
    * whether an unmarked file is AI-made
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .models import Status, TargetResult

MEDIA_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".heif", ".tif", ".tiff", ".svg",
    ".mp4", ".mov", ".m4v", ".m4a", ".mp3", ".wav",
}  # fmt: skip

MAX_BYTES = 64 * 1024 * 1024
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_C2PA_UUID = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")
_XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")

# IPTC Digital Source Type values that declare an AI origin.
AI_SOURCE_TYPES = {"trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia"}
_DST = re.compile(rb"digitalsourcetype/([A-Za-z]+)", re.IGNORECASE)

# PNG text-chunk keys written by image generators.
_PNG_GENERATOR_KEYS = {
    "parameters": "Stable Diffusion web UI parameters",
    "prompt": "ComfyUI prompt graph",
    "workflow": "ComfyUI workflow",
    "invokeai_metadata": "InvokeAI metadata",
    "sd-metadata": "InvokeAI metadata",
    "generation_data": "generation data",
    "dream": "InvokeAI dream command",
}

# Generator names as they appear in EXIF Software, XMP CreatorTool or C2PA claims.
_GENERATORS = [
    (re.compile(r"DALL[^A-Za-z0-9]{0,3}E", re.IGNORECASE), "DALL·E"),
    (re.compile(r"\bgpt-image\b", re.IGNORECASE), "OpenAI image model"),
    (re.compile(r"\bOpenAI\b"), "OpenAI"),
    (re.compile(r"\bMidjourney\b", re.IGNORECASE), "Midjourney"),
    (re.compile(r"\bStable ?Diffusion\b", re.IGNORECASE), "Stable Diffusion"),
    (re.compile(r"\bstability\.ai\b", re.IGNORECASE), "Stability AI"),
    (re.compile(r"\bAdobe Firefly\b", re.IGNORECASE), "Adobe Firefly"),
    (re.compile(r"\bComfyUI\b", re.IGNORECASE), "ComfyUI"),
    (re.compile(r"\bAUTOMATIC1111\b", re.IGNORECASE), "AUTOMATIC1111"),
    (re.compile(r"\bNovelAI\b", re.IGNORECASE), "NovelAI"),
    (re.compile(r"\bInvokeAI\b", re.IGNORECASE), "InvokeAI"),
    (re.compile(r"\bFooocus\b", re.IGNORECASE), "Fooocus"),
    (re.compile(r"\bLeonardo\.?Ai\b", re.IGNORECASE), "Leonardo AI"),
    (re.compile(r"\bImagen ?\d"), "Google Imagen"),
    (re.compile(r"\bMade with Google AI\b", re.IGNORECASE), "Google AI"),
    (re.compile(r"\bBing Image Creator\b", re.IGNORECASE), "Bing Image Creator"),
    (re.compile(r"\bMicrosoft Designer\b", re.IGNORECASE), "Microsoft Designer"),
    (re.compile(r"\bIdeogram\b", re.IGNORECASE), "Ideogram"),
    (re.compile(r"\bFLUX\.1\b"), "FLUX.1"),
    (re.compile(r"\bblack-forest-labs\b", re.IGNORECASE), "Black Forest Labs"),
    (re.compile(r"\bRunway(?:ML| Gen)", re.IGNORECASE), "Runway"),
    (re.compile(r"\bElevenLabs\b", re.IGNORECASE), "ElevenLabs"),
    (re.compile(r"\bSuno\b"), "Suno"),
    (re.compile(r"\bUdio\b"), "Udio"),
    (re.compile(r"\bRecraft\b"), "Recraft"),
    (re.compile(r"\bKling AI\b", re.IGNORECASE), "Kling AI"),
    (re.compile(r"\bPika Labs\b", re.IGNORECASE), "Pika"),
]


@dataclass
class MediaFacts:
    format: str = "unknown"
    c2pa: bool = False
    c2pa_ai: bool = False
    iptc_source_types: list[str] = field(default_factory=list)
    generator_hints: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def iptc_ai(self) -> bool:
        return any(v.lower() in AI_SOURCE_TYPES for v in self.iptc_source_types)

    @property
    def marked_ai(self) -> bool:
        return self.c2pa_ai or self.iptc_ai

    @property
    def ai_evident(self) -> bool:
        """True when anything in the file says an AI made or altered it."""
        return self.marked_ai or bool(self.generator_hints)

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "c2pa_manifest": self.c2pa,
            "c2pa_declares_ai": self.c2pa_ai,
            "iptc_digital_source_types": self.iptc_source_types,
            "generator_hints": self.generator_hints,
            "truncated": self.truncated,
        }


# ---------------------------------------------------------------------------
# Container walkers. Each collects metadata bytes and C2PA bytes.
# ---------------------------------------------------------------------------


def _walk_jpeg(data: bytes, meta: list[bytes], c2pa: list[bytes]) -> None:
    pos = 2
    size = len(data)
    while pos + 4 <= size:
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if marker in (0xDA, 0xD9):  # start of scan / end of image: no metadata after this
            break
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if length < 2:
            break
        body = data[pos + 4 : pos + 2 + length]
        if marker == 0xE1:  # APP1: EXIF or XMP
            meta.append(body)
        elif marker == 0xEB:  # APP11: JUMBF, where C2PA lives
            c2pa.append(body)
        elif marker in (0xED, 0xFE):  # APP13 (IPTC IIM) and comments
            meta.append(body)
        pos += 2 + length


def _walk_png(data: bytes, meta: list[bytes], c2pa: list[bytes], hints: list[str]) -> None:
    pos = 8
    size = len(data)
    while pos + 8 <= size:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"caBX":
            c2pa.append(body)
        elif kind in (b"tEXt", b"zTXt", b"iTXt"):
            key, text = _png_text(kind, body)
            label = _PNG_GENERATOR_KEYS.get(key.lower())
            if label and text.strip() and label not in hints:
                hints.append(label)
            meta.append(key.encode("utf-8", "replace") + b"\n" + text.encode("utf-8", "replace"))
        elif kind == b"eXIf":
            meta.append(body)
        elif kind == b"IEND":
            break
        pos += 12 + length


def _png_text(kind: bytes, body: bytes) -> tuple[str, str]:
    key, _, rest = body.partition(b"\x00")
    try:
        if kind == b"tEXt":
            text = rest
        elif kind == b"zTXt":
            text = zlib.decompress(rest[1:])
        else:  # iTXt: flag, method, language\0, translated keyword\0, text
            compressed = rest[:1] == b"\x01"
            rest = rest[2:]
            _, _, rest = rest.partition(b"\x00")
            _, _, rest = rest.partition(b"\x00")
            text = zlib.decompress(rest) if compressed else rest
    except (zlib.error, IndexError):
        text = b""
    return key.decode("latin-1"), text.decode("utf-8", "replace")


def _walk_riff(data: bytes, meta: list[bytes], c2pa: list[bytes]) -> None:
    pos = 12
    size = len(data)
    while pos + 8 <= size:
        kind = data[pos : pos + 4]
        length = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"C2PA":
            c2pa.append(body)
        elif kind in (b"XMP ", b"_PMX", b"EXIF", b"LIST", b"iXML", b"bext"):
            meta.append(body)
        pos += 8 + length + (length & 1)


def _walk_bmff(data: bytes, meta: list[bytes], c2pa: list[bytes]) -> None:
    pos = 0
    size = len(data)
    while pos + 8 <= size:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        header = 8
        if length == 1:
            if pos + 16 > size:
                break
            length = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
            header = 16
        elif length == 0:
            length = size - pos
        if length < header:
            break
        body = data[pos + header : pos + length]
        if kind == b"uuid":
            usertype, payload = body[:16], body[16:]
            if usertype == _C2PA_UUID:
                c2pa.append(payload)
            elif usertype == _XMP_UUID:
                meta.append(payload)
        elif kind in (b"moov", b"meta", b"udta") and len(body) <= 8 * 1024 * 1024:
            meta.append(body)
            if b"c2pa" in body and b"jumb" in body:  # HEIF/AVIF keep the manifest as a meta item
                c2pa.append(body)
        pos += length


def _id3_tag(data: bytes) -> bytes:
    if len(data) < 10 or data[:3] != b"ID3":
        return b""
    s = data[6:10]
    size = (s[0] & 0x7F) << 21 | (s[1] & 0x7F) << 14 | (s[2] & 0x7F) << 7 | (s[3] & 0x7F)
    return data[: 10 + size]


def _xmp_packets(data: bytes) -> list[bytes]:
    out: list[bytes] = []
    start = 0
    while True:
        a = data.find(b"<x:xmpmeta", start)
        if a < 0:
            break
        b = data.find(b"</x:xmpmeta>", a)
        if b < 0:
            break
        out.append(data[a : b + 12])
        start = b + 12
    return out


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def inspect(data: bytes) -> MediaFacts:
    """Read whatever provenance signals a file's container metadata holds."""
    facts = MediaFacts()
    meta: list[bytes] = []
    c2pa: list[bytes] = []
    hints: list[str] = []

    if data[:3] == b"\xff\xd8\xff":
        facts.format = "jpeg"
        _walk_jpeg(data, meta, c2pa)
    elif data[:8] == _PNG_SIG:
        facts.format = "png"
        _walk_png(data, meta, c2pa, hints)
    elif data[:4] == b"RIFF" and len(data) >= 12:
        facts.format = {b"WEBP": "webp", b"WAVE": "wav", b"AVI ": "avi"}.get(data[8:12], "riff")
        _walk_riff(data, meta, c2pa)
    elif data[4:8] == b"ftyp":
        brand = data[8:12]
        facts.format = {
            b"avif": "avif", b"heic": "heif", b"heix": "heif", b"mif1": "heif",
            b"qt  ": "mov", b"M4A ": "m4a", b"M4V ": "m4v",
        }.get(brand, "mp4")  # fmt: skip
        _walk_bmff(data, meta, c2pa)
    elif data[:3] == b"ID3":
        facts.format = "mp3"
        tag = _id3_tag(data)
        meta.append(tag)
        if b"c2pa" in tag.lower():
            c2pa.append(tag)
    elif data[:4] in (b"GIF8",):
        facts.format = "gif"
    elif data[:4] in (b"II*\x00", b"MM\x00*"):
        facts.format = "tiff"
    elif b"<svg" in data[:2048].lower():
        facts.format = "svg"
        meta.append(data)

    if not meta:
        meta.extend(_xmp_packets(data))

    # A manifest can span several segments; only the first carries the "c2pa"
    # label, so keep them all once any one of them has it.
    if not any(b"c2pa" in chunk.lower() for chunk in c2pa):
        c2pa = []
    facts.c2pa = bool(c2pa)

    c2pa_types = {m.decode("ascii") for chunk in c2pa for m in _DST.findall(chunk)}
    facts.c2pa_ai = any(v.lower() in AI_SOURCE_TYPES for v in c2pa_types)

    iptc_types: list[str] = []
    for chunk in meta:
        for value in _DST.findall(chunk):
            text = value.decode("ascii")
            if text not in iptc_types:
                iptc_types.append(text)
    facts.iptc_source_types = iptc_types

    searchable = "\n".join(chunk.decode("utf-8", "replace") for chunk in meta + c2pa)
    for pattern, name in _GENERATORS:
        if pattern.search(searchable) and name not in hints:
            hints.append(name)
    facts.generator_hints = hints
    return facts


def classify(facts: MediaFacts) -> tuple[str, Status, str, str]:
    """Turn the facts about one file into (rule_id, status, detail, evidence)."""
    if facts.marked_ai:
        marks = []
        if facts.c2pa_ai:
            marks.append("C2PA manifest with an AI source type")
        if facts.iptc_ai:
            ai_values = [v for v in facts.iptc_source_types if v.lower() in AI_SOURCE_TYPES]
            marks.append("IPTC Digital Source Type = " + ", ".join(ai_values))
        return ("MED-002", Status.PASS, "The file declares an AI origin in a standard machine-readable form.", "; ".join(marks))
    if facts.generator_hints:
        extra = " A C2PA manifest is present but does not declare an AI source type." if facts.c2pa else ""
        return (
            "MED-001",
            Status.GAP,
            "The file carries traces of an AI generator but no interoperable AI marking." + extra,
            "Generator traces: " + ", ".join(facts.generator_hints),
        )
    if facts.c2pa:
        return ("MED-003", Status.INFO, "A C2PA manifest is present and does not declare an AI source type.", "")
    return (
        "MED-004",
        Status.INFO,
        "No provenance metadata found. The scanner cannot tell whether this file is AI-made.",
        "",
    )


def read_limited(path: Path) -> tuple[bytes, bool]:
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    return data[:MAX_BYTES], len(data) > MAX_BYTES


def scan_file(path: Path) -> TargetResult:
    try:
        data, truncated = read_limited(path)
    except OSError as exc:
        return TargetResult(str(path), "media", error=str(exc))
    return scan_bytes(data, str(path), truncated)


def scan_bytes(data: bytes, target: str, truncated: bool = False) -> TargetResult:
    """Scan file content already in memory; ``target`` names it in the report."""
    result = TargetResult(target, "media")
    if not data:
        result.error = "file is empty"
        return result
    facts = inspect(data)
    facts.truncated = truncated
    result.facts = facts.to_dict()
    rule_id, status, detail, evidence = classify(facts)
    if truncated:
        detail += f" Only the first {MAX_BYTES // (1024 * 1024)} MB were read."
    result.add(rule_id, status, detail, evidence)
    return result


def scan_path(path: Path) -> list[TargetResult]:
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES)
        if not files:
            return [TargetResult(str(path), "media", error="no media files found in this folder")]
        return [scan_file(p) for p in files]
    return [scan_file(path)]
