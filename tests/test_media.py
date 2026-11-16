import struct
import zlib
from pathlib import Path

from ai_disclosure_scan import media
from ai_disclosure_scan.models import Status

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "media"

DST = b"http://cv.iptc.org/newscodes/digitalsourcetype/"
XMP_AI = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType="' + DST + b'trainedAlgorithmicMedia"/></x:xmpmeta>'
XMP_CAMERA = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType="' + DST + b'digitalCapture"/></x:xmpmeta>'


def jpeg(*segments):
    out = b"\xff\xd8"
    for marker, body in segments:
        out += bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body
    return out + b"\xff\xda\x00\x02" + b"\x00" * 16 + b"\xff\xd9"


def png(*chunks):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    return b"\x89PNG\r\n\x1a\n" + ihdr + b"".join(chunk(k, b) for k, b in chunks) + chunk(b"IEND", b"")


def test_examples_classify_as_documented():
    by_name = {Path(r.target).name: r.findings[0] for r in media.scan_path(EXAMPLES)}
    assert (by_name["marked-iptc.png"].rule_id, by_name["marked-iptc.png"].status) == ("MED-002", Status.PASS)
    assert (by_name["marked-iptc.jpg"].rule_id, by_name["marked-iptc.jpg"].status) == ("MED-002", Status.PASS)
    assert (by_name["generator-trace.png"].rule_id, by_name["generator-trace.png"].status) == ("MED-001", Status.GAP)
    assert (by_name["no-signal.png"].rule_id, by_name["no-signal.png"].status) == ("MED-004", Status.INFO)


def test_jpeg_xmp_with_ai_source_type():
    facts = media.inspect(jpeg((0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + XMP_AI)))
    assert facts.format == "jpeg" and facts.iptc_ai and facts.marked_ai and not facts.c2pa


def test_camera_source_type_is_not_an_ai_marking():
    facts = media.inspect(jpeg((0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + XMP_CAMERA)))
    assert facts.iptc_source_types == ["digitalCapture"]
    assert not facts.marked_ai
    assert media.classify(facts)[0] == "MED-004"


def test_jpeg_c2pa_manifest_declaring_ai_across_two_segments():
    first = b"JP\x00\x00\x00\x00\x00\x01" + b"jumb" + b"jumdc2pa\x00" + b"c2pa.assertions"
    second = b"JP\x00\x00\x00\x00\x00\x02" + DST + b"trainedAlgorithmicMedia"
    facts = media.inspect(jpeg((0xEB, first), (0xEB, second)))
    assert facts.c2pa and facts.c2pa_ai
    assert media.classify(facts)[:2] == ("MED-002", Status.PASS)


def test_c2pa_manifest_without_ai_source_type_is_context_only():
    facts = media.inspect(jpeg((0xEB, b"JP\x00\x00jumbjumdc2pa\x00c2pa.actions" + DST + b"digitalCapture")))
    assert facts.c2pa and not facts.c2pa_ai
    assert media.classify(facts)[:2] == ("MED-003", Status.INFO)


def test_composite_ai_source_type_counts():
    facts = media.inspect(jpeg((0xEB, b"jumbc2pa" + DST + b"compositeWithTrainedAlgorithmicMedia")))
    assert facts.c2pa_ai


def test_app11_without_c2pa_label_is_not_a_manifest():
    facts = media.inspect(jpeg((0xEB, b"JP\x00\x00jumbjumdsome-other-box")))
    assert not facts.c2pa


def test_exif_software_generator_hint():
    facts = media.inspect(jpeg((0xE1, b"Exif\x00\x00II*\x00" + b"Software\x00Midjourney v7\x00")))
    assert facts.generator_hints == ["Midjourney"]
    assert media.classify(facts)[:2] == ("MED-001", Status.GAP)


def test_png_text_chunks():
    sd = png((b"tEXt", b"parameters\x00a cat\nSteps: 20, Sampler: Euler"))
    assert media.inspect(sd).generator_hints == ["Stable Diffusion web UI parameters"]
    comfy = png((b"tEXt", b'prompt\x00{"3": {"class_type": "KSampler"}}'))
    assert "ComfyUI prompt graph" in media.inspect(comfy).generator_hints
    compressed = png((b"zTXt", b"parameters\x00\x00" + zlib.compress(b"a dog\nSteps: 30")))
    assert media.inspect(compressed).generator_hints
    plain = png((b"tEXt", b"Comment\x00Created with GIMP"))
    assert not media.inspect(plain).ai_evident


def test_png_xmp_and_c2pa_chunk():
    assert media.inspect(png((b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + XMP_AI))).iptc_ai
    assert media.inspect(png((b"caBX", b"jumbjumdc2pa\x00" + DST + b"trainedAlgorithmicMedia"))).c2pa_ai


def test_webp_riff_chunks():
    def riff(*chunks):
        body = b"WEBP"
        for kind, data in chunks:
            body += kind + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")
        return b"RIFF" + struct.pack("<I", len(body)) + body

    facts = media.inspect(riff((b"VP8 ", b"\x00" * 9), (b"XMP ", XMP_AI)))
    assert facts.format == "webp" and facts.iptc_ai
    facts = media.inspect(riff((b"C2PA", b"jumbc2pa" + DST + b"trainedAlgorithmicMedia")))
    assert facts.c2pa_ai


def test_mp4_uuid_boxes():
    def box(kind, body):
        return struct.pack(">I", len(body) + 8) + kind + body

    ftyp = box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2")
    c2pa = box(b"uuid", bytes.fromhex("d8fec3d61b0e483c92975828877ec481") + b"jumbc2pa" + DST + b"trainedAlgorithmicMedia")
    facts = media.inspect(ftyp + c2pa + box(b"mdat", b"\x00" * 32))
    assert facts.format == "mp4" and facts.c2pa_ai
    xmp = box(b"uuid", bytes.fromhex("be7acfcb97a942e89c71999491e3afac") + XMP_AI)
    assert media.inspect(ftyp + xmp).iptc_ai
    assert not media.inspect(ftyp + box(b"mdat", b"\x00" * 32)).ai_evident


def test_garbage_and_truncated_files_do_not_crash():
    for data in [b"", b"\xff\xd8\xff", b"\xff\xd8\xff\xe1\xff", b"\x89PNG\r\n\x1a\n\x00\x00", b"RIFF\x00\x00", b"\x00\x00\x00\x08ftyp", b"hello"]:
        facts = media.inspect(data)
        assert not facts.ai_evident


def test_missing_and_empty_files(tmp_path):
    assert media.scan_file(tmp_path / "nope.png").error
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert media.scan_file(empty).error
    assert media.scan_path(tmp_path)[0].target.endswith("empty.png")
