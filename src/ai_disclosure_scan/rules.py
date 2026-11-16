"""The rule catalogue, with the legal basis of every check.

Each rule carries:

* ``basis``  one or more pinpoint references. Every reference names its source,
  the exact place in it (paragraph and sentence), a paraphrase of what that
  place says, and a link, so a reader can open the source and check the rule
  against it.
* ``reading``  the step from the provision to what a script can observe. This
  part is the scanner's own interpretation, not the law, and is labelled so.

Sources are ranked by weight. Only "law" binds. "Official guidance" is the
Commission's own explanation. "Secondary summary" is a law firm's account of
the Commission's guidelines, used where this project has not verified the
point against the guidelines text itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    key: str
    weight: str  # "law" | "official guidance" | "voluntary code" | "secondary summary"
    title: str
    url: str


SOURCES: dict[str, Source] = {
    s.key: s
    for s in [
        Source(
            "act",
            "law",
            "Regulation (EU) 2024/1689 (AI Act), Article 50, consolidated text of 27 July 2026 "
            "(European Commission, AI Act Service Desk)",
            "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50",
        ),
        Source(
            "faq",
            "official guidance",
            "European Commission, FAQ: Transparency obligations under Article 50 of the AI Act",
            "https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act",
        ),
        Source(
            "guidelines",
            "official guidance",
            "European Commission, Guidelines on the implementation of the transparency obligations "
            "applicable to certain AI systems (Article 50 AI Act), 20 July 2026",
            "https://digital-strategy.ec.europa.eu/en/library/guidelines-transparency-obligations-providers-and-deployers-ai-systems",
        ),
        Source(
            "code",
            "voluntary code",
            "European Commission, Code of Practice on marking and labelling of AI-generated content, 10 June 2026",
            "https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content",
        ),
        Source(
            "wf",
            "secondary summary",
            "William Fry, 'Time Running Out as AI Transparency Guidelines Published' "
            "(a law firm's summary of the Commission Guidelines)",
            "https://www.williamfry.com/knowledge/time-running-out-as-ai-transparency-guidelines-published/",
        ),
    ]
}


@dataclass(frozen=True)
class Basis:
    source: str  # key into SOURCES
    pinpoint: str  # where to look in the source
    says: str  # paraphrase of what that place says

    def to_dict(self) -> dict[str, str]:
        src = SOURCES[self.source]
        return {
            "source": src.title,
            "weight": src.weight,
            "pinpoint": self.pinpoint,
            "says": self.says,
            "url": src.url,
        }


@dataclass(frozen=True)
class Rule:
    id: str
    paragraph: str  # Article 50 paragraph(s) the signal relates to
    duty_holder: str  # "provider" | "deployer"
    title: str
    why: str
    fix: str
    basis: tuple[Basis, ...]
    reading: str  # the scanner's own step from the provision to the signal

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "paragraph": self.paragraph,
            "duty_holder": self.duty_holder,
            "title": self.title,
            "why": self.why,
            "fix": self.fix,
            "basis": [b.to_dict() for b in self.basis],
            "scanner_reading": self.reading,
        }


# --- Pinpoints reused by several rules -------------------------------------

_ART_50_1 = Basis(
    "act",
    "Article 50(1), first sentence",
    "Providers must design and develop AI systems meant to interact directly with people so that those people "
    "are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, "
    "observant and circumspect person in the circumstances and context of use.",
)
_ART_50_5_TIMING = Basis(
    "act",
    "Article 50(5), first sentence",
    "The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and "
    "distinguishable manner, at the latest at the time of the first interaction or exposure.",
)
_ART_50_5_ACCESS = Basis(
    "act",
    "Article 50(5), second sentence",
    "The information must conform to the applicable accessibility requirements.",
)
_FAQ_INTERACTION = Basis(
    "faq",
    "Question 'When do providers of AI systems have to inform people they are interacting with an AI system?'",
    "Notice has to be given from the start of the first interaction, clearly and distinguishably. The 'obvious' "
    "exception is judged from the view of an average, reasonably well-informed person and is to be interpreted "
    "restrictively.",
)
_ART_50_2_MARK = Basis(
    "act",
    "Article 50(2), first sentence",
    "Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are "
    "marked in a machine-readable format and detectable as artificially generated or manipulated.",
)
_ART_50_2_QUALITY = Basis(
    "act",
    "Article 50(2), second sentence",
    "The technical solutions must be effective, interoperable, robust and reliable as far as technically feasible, "
    "considering the type of content, implementation costs and the generally acknowledged state of the art.",
)
_ART_50_2_EXCEPT = Basis(
    "act",
    "Article 50(2), third sentence",
    "The duty does not apply where the system only assists with standard editing, does not substantially alter "
    "the input data or its semantics, or is authorised by law for criminal-offence purposes.",
)
_FAQ_MARKING = Basis(
    "faq",
    "Question 'When do providers of AI systems have to mark the outputs of their generative AI systems and "
    "ensure their detectability?'",
    "Systems placed on the market before 2 August 2026 have a grace period for the marking and detection duty "
    "only, and must comply from 2 December 2026. The FAQ names no specific technique and points to the Code of "
    "Practice as one way to demonstrate compliance.",
)
_CODE_PROVIDERS = Basis(
    "code",
    "Section 1 (providers): marking and detection",
    "A voluntary code. Signatories who follow it can rely on its measures to demonstrate compliance; others "
    "must show their own measures are adequate.",
)
_ART_50_4_DEEPFAKE = Basis(
    "act",
    "Article 50(4), first subparagraph, first sentence",
    "Deployers of an AI system that generates or manipulates image, audio or video content constituting a deep "
    "fake must disclose that the content has been artificially generated or manipulated.",
)
_ART_50_4_ARTISTIC = Basis(
    "act",
    "Article 50(4), first subparagraph, third sentence",
    "For evidently artistic, creative, satirical, fictional or similar works, the duty is limited to disclosing "
    "the existence of such content in a way that does not hamper the display or enjoyment of the work.",
)
_ART_50_4_TEXT = Basis(
    "act",
    "Article 50(4), second subparagraph",
    "Deployers of an AI system that generates or manipulates text published to inform the public on matters of "
    "public interest must disclose that the text has been artificially generated or manipulated. This does not "
    "apply where the content has undergone human review or editorial control and a natural or legal person "
    "holds editorial responsibility for its publication.",
)
_FAQ_DEEPFAKE = Basis(
    "faq",
    "Question 'What is a deepfake and when do they need to be labelled?'",
    "The disclosure must be perceivable, for example through visible or audible labels, without specific tools "
    "or dedicated actions. Deployers cannot rely on the provider's embedded machine-readable marking to meet "
    "this duty.",
)
_FAQ_EDITORIAL = Basis(
    "faq",
    "Question 'What constitutes the human review or editorial control/responsibility required to qualify for "
    "an exemption from the labelling obligation?'",
    "Human review means substantive examination by people with relevant expertise; spell-checking and grammar "
    "correction do not count. Editorial responsibility means a person holds ultimate legal responsibility for "
    "the publication.",
)
_WF_GENERIC = Basis(
    "wf",
    "Section on Article 50(1) and AI agents",
    "Reports that, under the Commission Guidelines, generic references to an 'assistant', disclosures buried in "
    "terms and conditions, and machine-readable marks users cannot perceive are each insufficient on their own. "
    "Not verified against the Guidelines text by this project: check the Guidelines before relying on it.",
)

_STATIC_PAGE = (
    "The scanner recognises the widget by its script signature and searches the HTML the server sends for AI "
    "wording. It does not run JavaScript or open the widget, so a notice shown inside the widget is invisible "
    "to it. That is why page findings about chat are REVIEW, never GAP."
)

_RULES = [
    # --- Conversations: Article 50(1) with the timing rule of 50(5) -------------
    Rule(
        "INT-001",
        "50(1), 50(5)",
        "provider",
        "No AI disclosure anywhere in the conversation",
        "People must be told they are dealing with an AI system unless that is obvious, and the Commission reads "
        "the 'obvious' exception restrictively.",
        "Have the assistant say it is an AI in its first message, or show a clear, visible AI notice in the chat "
        "UI before the first reply (then scan with --ui-notice).",
        (_ART_50_1, _ART_50_5_TIMING, _FAQ_INTERACTION),
        "The scanner searches every assistant message for an explicit AI term (AI, bot, chatbot, artificial "
        "intelligence and equivalents in eight languages). Finding none, it reports that the transcript holds no "
        "disclosure. It cannot see a notice shown by the chat UI outside the message stream, and it does not "
        "judge whether the 'obvious' exception applies.",
    ),
    Rule(
        "INT-002",
        "50(5)",
        "provider",
        "AI disclosure arrives after the first reply",
        "The information has to be given at the latest at the time of the first interaction.",
        "Move the disclosure into the greeting or the first reply.",
        (_ART_50_5_TIMING, _FAQ_INTERACTION),
        "The scanner treats the assistant's first message as the first interaction. A disclosure that first "
        "appears in a later message is reported as late.",
    ),
    Rule(
        "INT-003",
        "50(1)",
        "provider",
        "Assistant claims to be human or denies being an AI",
        "A system that tells people it is a person gives them the opposite of the information the duty requires.",
        "Remove human-claim instructions from the prompt and add a rule that the assistant always confirms it is "
        "an AI when asked.",
        (_ART_50_1,),
        "Article 50 does not mention impersonation in so many words. The scanner reads a statement such as "
        "'I'm a real person' or 'I'm not a bot' as incompatible with informing people that they are interacting "
        "with an AI system.",
    ),
    Rule(
        "INT-004",
        "50(1), 50(5)",
        "provider",
        "Asked whether it is a bot, the assistant does not give a clear answer",
        "When someone asks directly, an evasive reply leaves them not knowing what they are talking to.",
        "Add a tested behaviour: any 'are you a bot / a human?' question gets a plain 'I'm an AI' answer.",
        (_ART_50_1, _ART_50_5_TIMING),
        "Article 50 contains no rule about answering direct questions. The scanner treats a direct question "
        "about AI status that gets no explicit answer as a sign the person was not informed in a clear manner.",
    ),
    Rule(
        "INT-005",
        "50(1), 50(5)",
        "provider",
        "Only a generic label such as 'virtual assistant' is used",
        "The information has to be clear and distinguishable. A generic 'assistant' label is reported to be "
        "insufficient on its own under the Commission Guidelines.",
        "Say 'AI' (or the local-language equivalent) in plain words: 'I'm an AI assistant'.",
        (_ART_50_1, _ART_50_5_TIMING, _WF_GENERIC),
        "The scanner separates explicit AI terms from generic labels (virtual, digital or smart assistant). "
        "A conversation with only a generic label is flagged for a person to judge, not as a gap, because the "
        "point rests on a secondary summary of the Guidelines.",
    ),
    Rule(
        "INT-010",
        "50(1), 50(5)",
        "provider",
        "AI disclosure present at the first interaction",
        "This is the signal the duty calls for.",
        "Nothing to fix. Keep a regression test so it stays that way.",
        (_ART_50_1, _ART_50_5_TIMING),
        "The assistant's first message contains an explicit AI term. The scanner does not judge prominence, "
        "wording quality or accessibility.",
    ),
    # --- Web pages: where the chat or voice surface lives ----------------------
    Rule(
        "PAGE-001",
        "50(1), 50(5)",
        "provider",
        "Chat or voice widget found, no AI wording in the page",
        "The page loads a conversational widget but nothing in its HTML tells visitors an AI is involved. The "
        "notice may still appear inside the widget, which a static scan cannot see.",
        "Open the widget and check its first message, or export a conversation and run the transcript scan. "
        "Add a visible AI notice next to the launcher if there is none.",
        (_ART_50_1, _ART_50_5_TIMING, _FAQ_INTERACTION),
        _STATIC_PAGE + " A widget from a live-chat platform may also be staffed by people only.",
    ),
    Rule(
        "PAGE-002",
        "50(5)",
        "provider",
        "AI is mentioned on the page, but not as a clear notice about the chat",
        "A marketing mention of AI is not the same as telling a visitor that the thing they are about to talk "
        "to is an AI.",
        "Add a short notice tied to the chat itself, for example 'You're chatting with our AI assistant'.",
        (_ART_50_5_TIMING,),
        _STATIC_PAGE + " It distinguishes a sentence about the chat ('you're chatting with our AI assistant') "
        "from AI wording elsewhere on the page.",
    ),
    Rule(
        "PAGE-003",
        "50(1), 50(5)",
        "provider",
        "Clear AI notice for the chat found",
        "This is the signal the duty calls for.",
        "Nothing to fix. Confirm the notice is also visible on mobile and to screen readers.",
        (_ART_50_1, _ART_50_5_TIMING, _ART_50_5_ACCESS),
        "The page's visible text, or the widget's inline configuration, contains a sentence that tells visitors "
        "the chat is an AI. The scanner does not check where on the screen it appears.",
    ),
    Rule(
        "PAGE-004",
        "50(5)",
        "provider",
        "AI wording exists only where visitors cannot see it",
        "The information has to be clear and distinguishable. Wording that sits only in hidden elements, "
        "attributes or metadata is not shown to most visitors.",
        "Put the notice in visible text near the chat launcher.",
        (_ART_50_5_TIMING, _ART_50_5_ACCESS, _WF_GENERIC),
        "The scanner separates visible text from hidden elements (display:none, aria-hidden, screen-reader-only "
        "classes), attribute text (alt, title, aria-label) and metadata. Screen-reader-only text does serve some "
        "users, so this is for a person to judge.",
    ),
    Rule(
        "PAGE-005",
        "50(1)",
        "provider",
        "No chat or voice widget recognised",
        "No known conversational widget signature was found in the page HTML. Widgets injected later by a tag "
        "manager, or built in-house, will not be recognised.",
        "If the page does have a chat, export a conversation and run the transcript scan.",
        (_ART_50_1,),
        "Absence of a known signature says nothing about whether Article 50(1) applies to the site.",
    ),
    # --- Media files: Article 50(2) --------------------------------------------
    Rule(
        "MED-001",
        "50(2)",
        "provider",
        "AI-generator traces, but no standard machine-readable AI marking in the metadata",
        "Outputs of generative systems must be marked in a machine-readable format and be detectable as "
        "artificially generated. The file carries tool-specific traces of an AI generator but none of the "
        "interoperable metadata markings this scanner reads.",
        "Enable Content Credentials (C2PA) or IPTC Digital Source Type marking in the generating system, and "
        "check that your CMS or CDN does not strip metadata on upload or resize.",
        (_ART_50_2_MARK, _ART_50_2_QUALITY, _ART_50_2_EXCEPT, _FAQ_MARKING, _CODE_PROVIDERS),
        "The duty sits with the provider of the generating system, not with whoever hosts the file, and the Act "
        "names no specific standard. The scanner reads two interoperable metadata markings: a C2PA manifest that "
        "declares an AI source type, and the IPTC Digital Source Type. 'Gap' here means neither was found. It "
        "does not rule out an invisible watermark, which only the vendor's detector can read, and it does not "
        "test the exceptions or the transition period.",
    ),
    Rule(
        "MED-002",
        "50(2)",
        "provider",
        "Standard machine-readable AI marking present",
        "The file declares an AI origin in an interoperable, machine-readable way.",
        "Nothing to fix. Metadata is one layer and is easily stripped; check it survives your publishing pipeline.",
        (_ART_50_2_MARK, _ART_50_2_QUALITY, _CODE_PROVIDERS),
        "The scanner found a C2PA manifest with an AI source type or an IPTC Digital Source Type of "
        "trainedAlgorithmicMedia / compositeWithTrainedAlgorithmicMedia. It does not verify the manifest's "
        "signature and does not test robustness.",
    ),
    Rule(
        "MED-003",
        "50(2)",
        "provider",
        "Provenance manifest present, AI origin not stated",
        "A C2PA manifest was found but it does not declare an AI source type. That is normal for camera "
        "originals and ordinary edits.",
        "Nothing to fix unless the file was in fact AI-generated.",
        (_ART_50_2_MARK,),
        "The scanner cannot tell whether the file is AI-made. It reports the manifest as context.",
    ),
    Rule(
        "MED-004",
        "50(2)",
        "provider",
        "No provenance signal in the file",
        "Nothing in the file's metadata says how it was made. The scanner cannot tell whether it is AI-generated.",
        "If this file came out of a generative system, its metadata marking is missing or was stripped.",
        (_ART_50_2_MARK,),
        "No C2PA manifest, no IPTC Digital Source Type and no generator traces. Invisible watermarks are not "
        "checked. This is context, not a finding against anyone.",
    ),
    # --- Labels people can see: Article 50(4) ----------------------------------
    Rule(
        "LBL-001",
        "50(4), 50(5)",
        "deployer",
        "AI-made media on the page, no visible AI label",
        "Deployers must disclose deep fakes in a way people can perceive without tools. Whether this media is a "
        "deep fake in the legal sense needs a human judgement.",
        "If the media depicts real-looking people, places or events, add a visible label (the Commission "
        "publishes EU icons for this).",
        (_ART_50_4_DEEPFAKE, _ART_50_4_ARTISTIC, _ART_50_5_TIMING, _FAQ_DEEPFAKE),
        "The scanner sees that media on the page is AI-made (by its marking or generator traces) and that the "
        "page's visible text has no AI label. It cannot judge whether the media is a deep fake as defined in "
        "Article 3(60), which is the condition for the duty, or whether the artistic exception applies.",
    ),
    Rule(
        "LBL-002",
        "50(4), 50(5)",
        "deployer",
        "AI-made media on the page, visible AI label found",
        "The page both carries AI-made media and tells visitors so.",
        "Nothing to fix. Check the label sits next to the media it refers to.",
        (_ART_50_4_DEEPFAKE, _ART_50_5_TIMING, _FAQ_DEEPFAKE),
        "The scanner found an AI label somewhere in the page's visible text. It does not check that the label "
        "is placed next to the media.",
    ),
    Rule(
        "LBL-003",
        "50(4), 50(5)",
        "deployer",
        "Page is declared AI-generated in metadata only",
        "The page's code declares AI-generated content, but visitors see no notice. AI-written text that informs "
        "the public on matters of public interest must be disclosed unless the editorial exception applies.",
        "Add a visible notice, or document the editorial review that makes the exception apply.",
        (_ART_50_4_TEXT, _ART_50_5_TIMING, _FAQ_EDITORIAL),
        "The scanner found a machine-readable declaration (a meta tag, a data-ai attribute or a JSON-LD "
        "digitalSourceType) and no visible AI label. Whether the text informs the public on a matter of public "
        "interest, and whether it had human editorial review, are for a person to establish.",
    ),
]

RULES: dict[str, Rule] = {rule.id: rule for rule in _RULES}


def get(rule_id: str) -> Rule:
    return RULES[rule_id]


def all_rules() -> list[Rule]:
    return list(_RULES)


def to_markdown() -> str:
    """The whole catalogue as a document: docs/article-50-mapping.md is generated from this."""
    lines = [
        "# How each check maps to Article 50",
        "",
        "Generated from the rule catalogue (`ai-disclosure-scan rules --format md`). Do not edit by hand.",
        "",
        "Every check lists the exact place in its source and a paraphrase of what that place says, so you can "
        "open the source and compare. Only sources marked **law** bind. The line *Scanner's reading* is this "
        "project's own step from the provision to something a script can observe; it is an interpretation, "
        "not the law.",
        "",
        "## Sources",
        "",
        "| Weight | Source |",
        "|---|---|",
    ]
    for src in SOURCES.values():
        lines.append(f"| {src.weight} | [{src.title}]({src.url}) |")
    lines += [
        "",
        "The official journal text of the Act is at <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>. "
        "Article 50 has applied since 2 August 2026.",
        "",
        "## Checks",
        "",
    ]
    for rule in _RULES:
        lines += [
            f"### {rule.id}: {rule.title}",
            "",
            f"Article {rule.paragraph} · duty holder: {rule.duty_holder}",
            "",
            "**Basis**",
            "",
        ]
        for basis in rule.basis:
            src = SOURCES[basis.source]
            lines.append(f"- *{src.weight}* · [{basis.pinpoint}]({src.url}): {basis.says}")
        lines += ["", f"**Scanner's reading:** {rule.reading}", "", f"**Usual fix:** {rule.fix}", ""]
    return "\n".join(lines)
