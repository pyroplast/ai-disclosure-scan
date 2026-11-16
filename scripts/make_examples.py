"""Build the example media under examples/.

The images are plain gradients drawn by this script. They are not AI-generated:
only their metadata imitates what real tools write, so the scanner has
something to read. Standard library only; the JPEG example needs Pillow and
is skipped when Pillow is not installed.

    python scripts/make_examples.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "examples"

XMP_AI = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/" '
    'Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/>'
    "</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
)

SD_PARAMETERS = (
    "a lighthouse on a cliff at dusk, oil painting, dramatic sky\n"
    "Negative prompt: blurry, low quality\n"
    "Steps: 28, Sampler: DPM++ 2M Karras, CFG scale: 6, Seed: 1840221, Size: 480x300, Model: sdxl_base_1.0"
)


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def gradient_png(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int], extra: list[bytes]) -> bytes:
    rows = bytearray()
    for y in range(height):
        t = y / max(1, height - 1)
        rows.append(0)  # filter: none
        for x in range(width):
            s = x / max(1, width - 1)
            for c in range(3):
                value = top[c] + (bottom[c] - top[c]) * t
                value += 18 * (s - 0.5)  # slight left-to-right drift
                rows.append(max(0, min(255, int(value))))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + b"".join(extra)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )


def text_chunk(key: str, value: str) -> bytes:
    return _chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1"))


def xmp_chunk(xmp: str) -> bytes:
    return _chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + xmp.encode("utf-8"))


def jpeg_with_xmp(width: int, height: int, xmp: str) -> bytes | None:
    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:
        return None
    image = Image.new("RGB", (width, height))
    for y in range(height):
        t = y / (height - 1)
        row = (int(30 + 60 * t), int(60 + 90 * t), int(110 + 100 * t))
        for x in range(width):
            image.putpixel((x, y), row)
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=80)
    data = buffer.getvalue()
    payload = b"http://ns.adobe.com/xap/1.0/\x00" + xmp.encode("utf-8")
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return data[:2] + segment + data[2:]  # right after the SOI marker


def main() -> None:
    dusk = ((38, 44, 84), (232, 142, 92))
    moss = ((52, 92, 70), (208, 214, 170))
    slate = ((70, 80, 96), (190, 198, 206))

    files = {
        # A file that says, in the standard way, that an AI made it.
        "media/marked-iptc.png": gradient_png(480, 300, *dusk, [xmp_chunk(XMP_AI)]),
        # A file with tool-specific generator traces and no standard marking.
        "media/generator-trace.png": gradient_png(480, 300, *moss, [text_chunk("parameters", SD_PARAMETERS)]),
        # A file with no provenance metadata at all.
        "media/no-signal.png": gradient_png(480, 300, *slate, []),
        # Page examples reuse the same three kinds of file.
        "sites/northwind-bad/img/hero.png": gradient_png(480, 300, *moss, [text_chunk("parameters", SD_PARAMETERS)]),
        "sites/northwind-bad/img/team.png": gradient_png(240, 160, *slate, []),
        "sites/northwind-good/img/hero.png": gradient_png(480, 300, *dusk, [xmp_chunk(XMP_AI)]),
        "sites/northwind-hidden/hero.png": gradient_png(240, 160, *slate, []),
    }
    jpeg = jpeg_with_xmp(480, 300, XMP_AI)
    if jpeg is not None:
        files["media/marked-iptc.jpg"] = jpeg
    else:
        print("Pillow not installed: skipping media/marked-iptc.jpg")

    for name, data in files.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT.parent)} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
