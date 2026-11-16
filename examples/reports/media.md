# AI disclosure scan

EU AI Act Article 50 readiness signals · generated 2026-11-16 19:36 UTC · ai-disclosure-scan 0.1.0

| Gaps | To review | Passed | Info | Scanned |
|---:|---:|---:|---:|---:|
| 1 | 0 | 2 | 1 | 4 |

## What to look at first

- **GAP** `MED-001` AI-generator traces, but no standard machine-readable AI marking in the metadata (Art. 50(2)): 1×

## Findings

### `examples/media/generator-trace.png` (media)

- **GAP** `MED-001` AI-generator traces, but no standard machine-readable AI marking in the metadata (Art. 50(2))
  - The file carries traces of an AI generator but no interoperable AI marking.
  - Evidence: `Generator traces: Stable Diffusion web UI parameters`
  - Fix: Enable Content Credentials (C2PA) or IPTC Digital Source Type marking in the generating system, and check that your CMS or CDN does not strip metadata on upload or resize.

### `examples/media/marked-iptc.jpg` (media)

- **PASS** `MED-002` Standard machine-readable AI marking present (Art. 50(2))
  - The file declares an AI origin in a standard machine-readable form.
  - Evidence: `IPTC Digital Source Type = trainedAlgorithmicMedia`

### `examples/media/marked-iptc.png` (media)

- **PASS** `MED-002` Standard machine-readable AI marking present (Art. 50(2))
  - The file declares an AI origin in a standard machine-readable form.
  - Evidence: `IPTC Digital Source Type = trainedAlgorithmicMedia`

### `examples/media/no-signal.png` (media)

- **INFO** `MED-004` No provenance signal in the file (Art. 50(2))
  - No provenance metadata found. The scanner cannot tell whether this file is AI-made.

## Legal basis of these checks

Each check names the exact place in its source. Only sources marked *law* bind; the scanner's reading is this tool's interpretation.

**`MED-001` AI-generator traces, but no standard machine-readable AI marking in the metadata**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.
- *law* · [Article 50(2), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The technical solutions must be effective, interoperable, robust and reliable as far as technically feasible, considering the type of content, implementation costs and the generally acknowledged state of the art.
- *law* · [Article 50(2), third sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The duty does not apply where the system only assists with standard editing, does not substantially alter the input data or its semantics, or is authorised by law for criminal-offence purposes.
- *official guidance* · [Question 'When do providers of AI systems have to mark the outputs of their generative AI systems and ensure their detectability?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Systems placed on the market before 2 August 2026 have a grace period for the marking and detection duty only, and must comply from 2 December 2026. The FAQ names no specific technique and points to the Code of Practice as one way to demonstrate compliance.
- *voluntary code* · [Section 1 (providers): marking and detection](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content): A voluntary code. Signatories who follow it can rely on its measures to demonstrate compliance; others must show their own measures are adequate.
- *Scanner's reading (not the law):* The duty sits with the provider of the generating system, not with whoever hosts the file, and the Act names no specific standard. The scanner reads two interoperable metadata markings: a C2PA manifest that declares an AI source type, and the IPTC Digital Source Type. 'Gap' here means neither was found. It does not rule out an invisible watermark, which only the vendor's detector can read, and it does not test the exceptions or the transition period.

**`MED-002` Standard machine-readable AI marking present**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.
- *law* · [Article 50(2), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The technical solutions must be effective, interoperable, robust and reliable as far as technically feasible, considering the type of content, implementation costs and the generally acknowledged state of the art.
- *voluntary code* · [Section 1 (providers): marking and detection](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content): A voluntary code. Signatories who follow it can rely on its measures to demonstrate compliance; others must show their own measures are adequate.
- *Scanner's reading (not the law):* The scanner found a C2PA manifest with an AI source type or an IPTC Digital Source Type of trainedAlgorithmicMedia / compositeWithTrainedAlgorithmicMedia. It does not verify the manifest's signature and does not test robustness.

**`MED-004` No provenance signal in the file**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.
- *Scanner's reading (not the law):* No C2PA manifest, no IPTC Digital Source Type and no generator traces. Invisible watermarks are not checked. This is context, not a finding against anyone.

---

This is a technical readiness check, not legal advice and not a compliance verdict. It reports signals a script can see; whether a duty under Article 50 applies to you, and whether you meet it, needs a person who knows your system.

