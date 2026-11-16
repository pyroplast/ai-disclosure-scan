# What the scanner can and cannot tell you

The scanner is a set of heuristics. This page says where each one stops, so you know how much weight a finding carries.

## Conversations

**What it does.** It reads exported conversations and looks at the assistant's messages for explicit AI terms, generic labels, human claims and answers to "are you a bot?" questions.

**Where it stops.**

- *The first message is treated as the first interaction.* If your product shows an AI notice in the chat UI before any message, the transcript will not contain it. Pass `--ui-notice` to say so. The scanner takes your word for it and reports the check as not performed.
- *Term matching, not understanding.* "AI" in the first message counts as a disclosure even if the sentence is about something else ("our AI features include…"). A false pass is possible. Read the evidence line.
- *The "obvious" exception is not assessed.* Article 50(1) does not require a notice where the AI nature is obvious. The Commission says to read that restrictively, and the scanner does not try to apply it.
- *Eight languages.* English, Spanish, German, French, Italian, Portuguese, Dutch and Polish. A conversation in another language will look like it has no disclosure.
- *Plain-text exports are guessed.* Speaker labels such as `User:` and `Agent:` are recognised. When a file only has names (`Maria:`, `Tom:`), the first speaker is assumed to be the visitor and the result carries `roles_guessed: true`.
- *Role is not assessed.* The duty in Article 50(1) is the provider's. The scanner does not know whether you are the provider.

## Web pages

**What it does.** It fetches one HTML document, recognises chat and voice widgets by script signature, and searches the text for an AI notice. It separates visible text from hidden elements, attribute text and metadata. It downloads up to 12 media files from the page and inspects their metadata.

**Where it stops.**

- *No JavaScript.* A notice rendered by script, a widget injected by a tag manager, and everything inside the widget are invisible. This is why page findings about chat are `REVIEW` and never `GAP`.
- *Signatures go stale.* The widget list holds 34 vendors and their script hosts as known when this version was written. In-house chat UIs are not recognised.
- *A live-chat widget is not proof of an AI.* Many platforms can be staffed by people only.
- *Visibility is approximated.* `hidden`, `aria-hidden="true"`, inline `display:none` / `visibility:hidden`, `<noscript>` and a few screen-reader-only class names are treated as hidden. Text hidden by an external stylesheet is treated as visible.
- *Labels are matched page-wide.* An "AI-generated" label anywhere in the visible text counts for all AI-made media on the page. The scanner does not check that the label sits next to the media.
- *CDNs strip metadata.* Many sites serve re-encoded images without metadata. The original may have been marked.

## Media files

**What it does.** It walks the container (JPEG segments, PNG chunks, RIFF chunks, ISO BMFF boxes, ID3 tags) and looks for a C2PA manifest, an IPTC Digital Source Type and tool-specific generator traces.

**Where it stops.**

- *Metadata only.* Invisible watermarks (SynthID and others) need the vendor's detector. A `GAP` on `MED-001` means none of the metadata markings this tool reads were found, on a file that carries traces of an AI generator. It does not mean the file has no marking at all.
- *No signature check.* A C2PA manifest is detected by its label and searched for an AI source type. Its signature and hashes are not validated. Use `c2patool` for that.
- *No verdict on unmarked files.* A file with no provenance metadata gets `INFO`. The scanner never guesses from pixels whether something is AI-made.
- *The duty holder is not assessed.* Article 50(2) binds the provider of the generating system, with exceptions and a transition period to 2 December 2026 for systems already on the market on 2 August 2026. The scanner looks at a file, not at who made it or when the system was placed on the market.
- *Text outputs.* Article 50(2) also covers generated text. Marking of text is not checked.

## Not covered at all

- Article 50(3): emotion recognition and biometric categorisation.
- Whether content is a deep fake under Article 3(60), whether text concerns a matter of public interest, and whether the artistic or editorial exceptions apply.
- Accessibility of a notice beyond the hidden/visible split (contrast, size, screen-reader behaviour).
- Obligations outside Article 50, including the high-risk regime, the GPAI rules and national law.

## On the sources

Rules cite Article 50 from the consolidated text of 27 July 2026 on the Commission's AI Act Service Desk, and the Commission's FAQ on Article 50. The paraphrases in the catalogue are this project's wording. Where a paraphrase and the source differ, the source wins: follow the link.

One point, that a generic "assistant" label and hidden notices are insufficient on their own, is taken from a law firm's summary of the Commission Guidelines and has not been verified against the Guidelines text. It is marked `secondary summary` wherever it appears, and the rules that use it only produce `REVIEW`.
