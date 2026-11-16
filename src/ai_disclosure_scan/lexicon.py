"""Phrase lists and widget signatures the checks rely on.

Everything here is a heuristic. The lists cover English, Spanish, German,
French, Italian, Portuguese, Dutch and Polish, and they are meant to be
extended: a missed phrase is a pull request, not a design flaw.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_I = re.IGNORECASE


def _c(patterns: list[str], flags: int = _I) -> list[re.Pattern[str]]:
    return [re.compile(p, flags) for p in patterns]


# ---------------------------------------------------------------------------
# 1. The assistant says it is an AI (explicit)
# ---------------------------------------------------------------------------

# Upper-case acronyms are matched case-sensitively: lower-case "ai" is an
# ordinary word in Italian, French and Portuguese.
_EXPLICIT_CASED = _c(
    [
        r"(?<![\w.])A\.?I\.?(?![\w])",  # AI, A.I.
        r"(?<![\w.])I\.?A\.?(?![\w])",  # IA (es, fr, it, pt)
        r"(?<![\w.])KI(?![\w])",  # KI (de)
    ],
    flags=0,
)

_EXPLICIT = _c(
    [
        # English
        r"\ban ai\b",
        r"\bai[- ](?:assistant|agent|chatbot|bot|model|system|powered|generated|concierge|helper|companion)\b",
        r"\bartificial intelligence\b",
        r"\bchat ?bot\b",
        r"\bbot\b",
        r"\blanguage model\b",
        r"\bautomated (?:assistant|agent|system|chat|service|responder|response|helper|support)\b",
        r"\bnot (?:a|an) (?:real )?(?:human|person)\b",
        # Spanish
        r"\b(?:una|con|de|por) ia\b",
        r"\binteligencia artificial\b",
        r"\basistente automatizad[oa]\b",
        r"\bsistema automatizado\b",
        r"\bmodelo de lenguaje\b",
        r"\bno soy (?:una? )?(?:persona|human[oa])\b",
        # German
        r"\b(?:eine|einer|mit) ki\b",
        r"\bki-(?:assistent(?:in)?|agent|chatbot|bot|modell|system)\b",
        r"\bkünstliche[rn]? intelligenz\b",
        r"\bsprachmodell\b",
        r"\bkein (?:echter )?mensch\b",
        # French
        r"\b(?:une|par) ia\b",
        r"\b[ld]['’]ia\b",
        r"\bintelligence artificielle\b",
        r"\bagent conversationnel\b",
        r"\bassistante? automatisée?\b",
        r"\bmodèle de langage\b",
        r"\bpas (?:une? )?(?:humaine?|personne réelle|vraie personne)\b",
        # Italian
        r"\bun['’]ia\b",
        r"\b(?:una|con) ia\b",
        r"\bintelligenza artificiale\b",
        r"\bassistente automatic[oa]\b",
        r"\bmodello linguistico\b",
        r"\bnon sono (?:una? )?(?:persona|uman[oa])\b",
        # Portuguese
        r"\buma ia\b",
        r"\binteligência artificial\b",
        r"\bmodelo de linguagem\b",
        r"\bnão sou (?:uma? )?(?:pessoa|human[oa])\b",
        # Dutch
        r"\bai-(?:assistent|agent|chatbot|bot|model)\b",
        r"\bkunstmatige intelligentie\b",
        r"\btaalmodel\b",
        r"\bgeen (?:echt )?(?:mens|persoon)\b",
        # Polish
        r"\bsztuczn(?:a|ą|ej) inteligencj(?:a|ą|i|ę)\b",
        r"\basystent(?:em|ka|ką)? ai\b",
        r"\bchatbot(?:em)?\b",
        r"\bbot(?:em)?\b",
        r"\bnie jestem (?:człowiekiem|osobą)\b",
    ]
)

# ---------------------------------------------------------------------------
# 2. Generic labels that do not say "AI" (weak)
# ---------------------------------------------------------------------------

_WEAK = _c(
    [
        r"\b(?:virtual|digital|smart|online|automatic) (?:assistant|agent|helper|concierge|advisor)\b",
        r"\b(?:asistente|agente) (?:virtual|digital)\b",
        r"\b(?:virtueller?|digitaler?) (?:assistent(?:in)?|berater(?:in)?|helfer)\b",
        r"\bassistante? (?:virtuel(?:le)?|numérique|digitale?)\b",
        r"\bassistente (?:virtuale|digitale|virtual|digital)\b",
        r"\b(?:virtuele|digitale) (?:assistent|medewerker)\b",
        r"\bwirtualn(?:y|ym|a|ą) asystent(?:em|ka|ką)?\b",
    ]
)

# ---------------------------------------------------------------------------
# 3. The assistant says it is a person, or denies being a machine
# ---------------------------------------------------------------------------

_HUMAN_CLAIM = _c(
    [
        # English
        r"\bI(?:['’]m| am) (?:a |an )?(?:real |actual |live )?(?:human being|human agent|human|person|live agent)\b",
        r"\bnot (?:a |an )?(?:bot|chat ?bot|robot|ai|a\.i\.|machine|computer|automated \w+)\b",
        r"\b(?:yes|yep|yeah|of course)[,!.]? (?:I(?:['’]m| am) )?(?:a )?(?:real |actual )?(?:human|person)\b",
        r"\b(?:talking|speaking|chatting) (?:to|with) a (?:real |actual |live )?(?:human|person)\b",
        r"\breal (?:human|person) here\b",
        r"\bI(?:['’]m| am) (?-i:[A-ZÀ-Þ][a-zà-ÿ]+),? (?:a |an )?(?:real |actual |live )?(?:human being|human|person)\b",
        # Spanish
        r"(?<!\bno )\bsoy (?:una? )?(?:persona|human[oa]|agente human[oa])\b",
        r"\bno soy (?:una? )?(?:bot|robot|chatbot|ia|máquina|inteligencia artificial)\b",
        # German
        r"\bich bin (?:ein |eine )?(?:echter |echte |richtiger )?(?:mensch|menschlicher? mitarbeiter(?:in)?)\b",
        r"\bkein(?:e)? (?:bot|roboter|chatbot|ki|maschine)\b",
        # French
        r"\bje suis (?:une? )?(?:vraie? )?(?:personne|humaine?|être humain)\b",
        r"\bje ne suis pas (?:une? )?(?:bot|robot|chatbot|ia|machine)\b",
        # Italian
        r"(?<!\bnon )\bsono (?:una? )?(?:persona|uman[oa])\b",
        r"\bnon sono (?:una? )?(?:bot|robot|chatbot|ia|macchina)\b",
        # Portuguese
        r"(?<!\bnão )\bsou (?:uma? )?(?:pessoa|human[oa])\b",
        r"\bnão sou (?:uma? )?(?:bot|robô|chatbot|ia|máquina)\b",
        # Dutch
        r"\bik ben (?:een )?(?:echt |echte )?(?:mens|persoon)\b",
        r"\bgeen (?:bot|robot|chatbot|ai|machine)\b",
        # Polish
        r"(?<!\bnie )\bjestem (?:prawdziwym |prawdziwą )?(?:człowiekiem|osobą)\b",
        r"\bnie jestem (?:botem|robotem|chatbotem|maszyną|ai)\b",
    ]
)

# ---------------------------------------------------------------------------
# 4. The user asks what they are talking to
# ---------------------------------------------------------------------------

_IDENTITY_QUESTION = _c(
    [
        # English
        r"\b(?:are|r) (?:you|u) (?:an? )?(?:real |actual )?(?:bot|chat ?bot|robot|human|person|ai|machine|computer|real)\b",
        r"\b(?:am i|is this) (?:talking |speaking |chatting )?(?:to |with )?(?:an? )?(?:real |actual )?(?:bot|chat ?bot|robot|human|person|ai|machine|automated)\b",
        r"\b(?:is|was) (?:this|that) (?:an? )?(?:bot|ai|automated|real person)\b",
        # Spanish
        r"\b(?:eres|es usted|sos) (?:una? )?(?:bot|robot|human[oa]|persona|ia|máquina)\b",
        r"\b(?:hablo|estoy hablando) con (?:una? )?(?:bot|robot|human[oa]|persona|máquina|ia)\b",
        # German
        r"\b(?:bist du|sind sie) (?:ein |eine )?(?:echter |echte )?(?:bot|roboter|mensch|ki|maschine)\b",
        r"\bspreche ich mit (?:einem |einer )?(?:bot|roboter|menschen|ki|maschine)\b",
        # French
        r"\b(?:es-tu|êtes-vous|tu es|vous êtes) (?:une? )?(?:bot|robot|humaine?|personne|ia|machine)\b",
        r"\bje parle (?:à|avec) (?:une? )?(?:bot|robot|humaine?|personne|ia|machine)\b",
        # Italian
        r"\bsei (?:una? )?(?:bot|robot|uman[oa]|persona|ia|macchina)\b",
        r"\bsto parlando con (?:una? )?(?:bot|robot|uman[oa]|persona|ia|macchina)\b",
        # Portuguese
        r"\b(?:você é|tu és|és) (?:uma? )?(?:bot|robô|human[oa]|pessoa|ia|máquina)\b",
        r"\bestou (?:falando|a falar) com (?:uma? )?(?:bot|robô|human[oa]|pessoa|ia|máquina)\b",
        # Dutch
        r"\b(?:ben je|bent u) (?:een )?(?:bot|robot|mens|persoon|ai|machine)\b",
        # Polish
        r"\b(?:jesteś|jest pan|jest pani) (?:botem|robotem|człowiekiem|ai|maszyną)\b",
        r"\brozmawiam z (?:botem|robotem|człowiekiem|ai|maszyną)\b",
    ]
)

# ---------------------------------------------------------------------------
# 5. A notice on a web page that the chat is an AI
# ---------------------------------------------------------------------------

_AI_NOUN = r"(?:ai|a\.i\.|artificial intelligence|generative ai|bot|chat ?bot|virtual assistant|automated \w+)"

_CHAT_NOTICE = _c(
    [
        # English
        r"\b(?:chatting|talking|speaking|interacting) (?:with|to) (?:[\w'’-]+,? ){0,5}?" + _AI_NOUN + r"\b",
        r"\b(?:this|our|the) (?:chat|assistant|chatbot|agent|service|conversation|helper) (?:is|uses|is powered by|is operated by|is run by) (?:an? )?"
        + _AI_NOUN
        + r"\b",
        r"\bpowered by (?:generative )?(?:ai|artificial intelligence)\b",
        r"\b(?:answers|responses|replies|messages) (?:are|may be) (?:generated|written|produced) by (?:an? )?(?:ai|artificial intelligence|automated \w+)\b",
        r"\bai[- ]generated (?:answers|responses|replies)\b",
        r"\b(?:ask|chat with|talk to|meet|message) (?:our |the |your )?(?:[\w'’-]+,? ){0,3}?(?:ai (?:assistant|agent|chatbot|bot|concierge)|chat ?bot|bot)\b",
        r"\bI(?:['’]m| am) (?:[\w'’-]+,? ){0,4}?(?:ai|a\.i\.|bot|chat ?bot|automated \w+)\b",
        # Spanish
        r"\best[aá]s? (?:hablando|chateando|conversando) con (?:una?|nuestr[oa]|el|la) (?:[\w'’-]+,? ){0,3}?(?:ia|inteligencia artificial|bot|chatbot|asistente virtual)\b",
        r"\b(?:respuestas|mensajes) generad[oa]s por (?:una? )?(?:ia|inteligencia artificial)\b",
        r"\b(?:con tecnología de|impulsado por|funciona con) (?:ia|inteligencia artificial)\b",
        r"\bsoy (?:[\w'’-]+,? ){0,4}?(?:ia|inteligencia artificial|bot|chatbot)\b",
        # German
        r"\bsie (?:chatten|sprechen|schreiben) mit (?:einem|einer|unserem|unserer) (?:[\w'’-]+,? ){0,3}?(?:ki|ki-\w+|bot|chatbot|künstlichen intelligenz)\b",
        r"\bki-generierte (?:antworten|nachrichten)\b",
        r"\b(?:antworten|nachrichten) werden (?:von|durch) (?:einer? )?ki (?:generiert|erstellt)\b",
        r"\bich bin (?:[\w'’-]+,? ){0,4}?(?:ki|ki-\w+|bot|chatbot)\b",
        # French
        r"\bvous (?:discutez|parlez|échangez|conversez) avec (?:une?|notre) (?:[\w'’-]+,? ){0,3}?(?:ia|intelligence artificielle|bot|chatbot|assistant virtuel)\b",
        r"\bréponses générées par (?:une? |l['’])?(?:ia|intelligence artificielle)\b",
        r"\bpropulsé par (?:l['’])?(?:ia|intelligence artificielle)\b",
        r"\bje suis (?:[\w'’-]+,? ){0,4}?(?:ia|intelligence artificielle|bot|chatbot)\b",
        # Italian
        r"\bstai (?:parlando|chattando) con (?:una?|il nostro|la nostra) (?:[\w'’-]+,? ){0,3}?(?:ia|intelligenza artificiale|bot|chatbot|assistente virtuale)\b",
        r"\brisposte generate (?:da|dall['’]) ?(?:ia|intelligenza artificiale)\b",
        # Portuguese
        r"\b(?:você está|estás) (?:falando|a falar|conversando) com (?:uma?|o nosso|a nossa|nosso|nossa) (?:[\w'’-]+,? ){0,3}?(?:ia|inteligência artificial|bot|chatbot|assistente virtual)\b",
        r"\brespostas geradas por (?:ia|inteligência artificial)\b",
        # Dutch
        r"\b(?:je|u) (?:chat|praat|spreekt) met (?:een|onze) (?:[\w'’-]+,? ){0,3}?(?:ai|ai-\w+|bot|chatbot|kunstmatige intelligentie)\b",
        r"\bantwoorden (?:zijn |worden )?gegenereerd door ai\b",
        # Polish
        r"\brozmawiasz z (?:[\w'’-]+,? ){0,3}?(?:ai|botem|chatbotem|sztuczną inteligencją|asystentem ai)\b",
        r"\bodpowiedzi (?:są )?generowane przez (?:ai|sztuczną inteligencję)\b",
    ]
)

# ---------------------------------------------------------------------------
# 6. A visible label saying content is AI-made
# ---------------------------------------------------------------------------

_AI_LABEL = _c(
    [
        r"\bai[- ](?:generated|manipulated|altered|edited|created|made|enhanced)\b",
        r"\b(?:generated|created|made|produced|edited|enhanced|altered|manipulated) (?:with|by|using) (?:ai|artificial intelligence|generative ai)\b",
        r"\bartificially (?:generated|manipulated)\b",
        r"\bsynthetic (?:media|image|video|audio|voice|content)\b",
        r"\bdeep ?fake\b",
        r"\b(?:generad|cread|manipulad)[oa]s? (?:por|con|mediante) (?:ia|inteligencia artificial)\b",
        r"\bki-(?:generiert|erstellt|erzeugt)\w*\b",
        r"\bmit (?:hilfe von )?ki (?:erstellt|generiert|erzeugt)\b",
        r"\bkünstlich (?:erzeugt|generiert)\b",
        r"\b(?:généré|créé|modifié)e?s? (?:par|avec) (?:une? |l['’])?(?:ia|intelligence artificielle)\b",
        r"\b(?:generat|creat)[oaie] (?:da|con|dall['’]) ?(?:ia|intelligenza artificiale)\b",
        r"\b(?:gerad|criad)[oa]s? (?:por|com) (?:ia|inteligência artificial)\b",
        r"\bai-gegenereerd\w*\b",
        r"\bgegenereerd (?:door|met) (?:ai|kunstmatige intelligentie)\b",
        r"\bwygenerowan[eyoa] przez (?:ai|sztuczną inteligencję)\b",
    ]
)

# ---------------------------------------------------------------------------
# 7. Persona names: "Hi, I'm Sarah"
# ---------------------------------------------------------------------------

_PERSONA = re.compile(
    r"(?i:\bI['’]?m|\bI am|\bmy name is|\bthis is|\bsoy|\bme llamo|\bmi nombre es|\bich bin|\bmein name ist"
    r"|\bje suis|\bje m['’]appelle|\bsono|\bmi chiamo|\bsou|\bmeu nome é|\bik ben|\bmam na imię|\bjestem)"
    r"\s+([A-ZÀ-Þ][a-zà-ÿ]{1,15})\b"
)

_NOT_A_NAME = {
    "Ai", "An", "A", "The", "Your", "Here", "Happy", "Glad", "Sorry", "Not", "Sure", "Available", "Ready",
    "Afraid", "Unable", "Able", "Still", "Just", "Always", "Going", "Looking", "Checking", "Una", "Un", "El",
    "La", "Tu", "Ein", "Eine", "Der", "Die", "Dein", "Ihr", "Une", "Votre", "Ton", "Il", "Lo", "Uma", "Um",
    "Een", "De", "Je", "Bot", "Chatbot", "Assistant", "Virtual", "Asistente", "Assistente", "Assistent",
    "Our", "This", "That", "So", "Very", "Really", "Now", "Back", "Also", "Only", "Now",
}  # fmt: skip


@dataclass(frozen=True)
class Hit:
    text: str
    start: int
    end: int


def _find(patterns: list[re.Pattern[str]], text: str) -> list[Hit]:
    hits: list[Hit] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            hits.append(Hit(match.group(0), match.start(), match.end()))
    hits.sort(key=lambda h: (h.start, -(h.end - h.start)))
    # Drop hits nested inside an earlier, longer hit.
    out: list[Hit] = []
    for hit in hits:
        if out and hit.start < out[-1].end:
            continue
        out.append(hit)
    return out


def _mask(text: str, hits: list[Hit]) -> str:
    chars = list(text)
    for hit in hits:
        for i in range(hit.start, hit.end):
            chars[i] = " "
    return "".join(chars)


def find_human_claims(text: str) -> list[Hit]:
    """Places where the speaker says it is a person or denies being a machine."""
    return _find(_HUMAN_CLAIM, text)


def find_explicit(text: str) -> list[Hit]:
    """Plain statements that an AI is involved.

    Denials are masked first, so "I'm not a bot" never counts as a disclosure
    just because it contains the word "bot".
    """
    masked = _mask(text, find_human_claims(text))
    return _find(_EXPLICIT_CASED + _EXPLICIT, masked)


def find_weak(text: str) -> list[Hit]:
    """Generic labels ("virtual assistant") that stop short of saying AI."""
    return _find(_WEAK, text)


def is_identity_question(text: str) -> bool:
    return bool(_find(_IDENTITY_QUESTION, text))


def find_chat_notice(text: str) -> list[Hit]:
    """Sentence-level notices that the chat itself is an AI."""
    masked = _mask(text, find_human_claims(text))
    return _find(_CHAT_NOTICE, masked)


def find_ai_label(text: str) -> list[Hit]:
    """Visible labels saying content was made or altered with AI."""
    return _find(_AI_LABEL, text)


def find_persona_name(text: str) -> str:
    for match in _PERSONA.finditer(text):
        name = match.group(1)
        if name.capitalize() not in _NOT_A_NAME:
            return name
    return ""


def snippet(text: str, hit: Hit, pad: int = 70) -> str:
    start = max(0, hit.start - pad)
    end = min(len(text), hit.end + pad)
    out = " ".join(text[start:end].split())
    if start > 0:
        out = "…" + out
    if end < len(text):
        out = out + "…"
    return out


# ---------------------------------------------------------------------------
# 8. Chat and voice widget signatures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Vendor:
    name: str
    kind: str  # "ai" (AI-first product) | "chat" (live chat that may or may not be AI) | "voice"
    needles: tuple[str, ...]  # lower-case substrings of script/iframe URLs or inline code
    tags: tuple[str, ...] = ()  # custom element names


VENDORS: tuple[Vendor, ...] = (
    # AI-first chat products
    Vendor("Botpress", "ai", ("cdn.botpress.cloud", "mediafiles.botpress.cloud", "botpresswebchat")),
    Vendor("Voiceflow", "ai", ("cdn.voiceflow.com", "voiceflow.chat.load")),
    Vendor("Chatbase", "ai", ("chatbase.co/embed", "www.chatbase.co")),
    Vendor("Ada", "ai", ("static.ada.support",)),
    Vendor("Dialogflow Messenger", "ai", ("dialogflow-console/fast/messenger", "df-messenger"), ("df-messenger",)),
    Vendor("IBM watsonx Assistant", "ai", ("assistant.watson.appdomain.cloud", "watsonassistantchatoptions")),
    Vendor("Landbot", "ai", ("cdn.landbot.io", "static.landbot.io")),
    Vendor("Kommunicate", "ai", ("widget.kommunicate.io",)),
    Vendor("DocsBot", "ai", ("widget.docsbot.ai",)),
    Vendor("SiteGPT", "ai", ("sitegpt.ai/widget", "widget.sitegpt.ai")),
    Vendor("CustomGPT", "ai", ("cdn.customgpt.ai",)),
    Vendor("Chatling", "ai", ("chatling.ai/js/embed",)),
    Vendor("Typebot", "ai", ("typebot.io", "@typebot.io/js")),
    Vendor("ManyChat", "ai", ("widget.manychat.com",)),
    Vendor("Copilot Studio", "ai", ("copilotstudio.microsoft.com", "powerva.microsoft.com")),
    # Voice agents
    Vendor("ElevenLabs Conversational AI", "voice", ("elevenlabs.io/convai-widget", "convai-widget"), ("elevenlabs-convai",)),
    Vendor("Vapi", "voice", ("vapi-ai/client-sdk-web", "vapi.ai/widget"), ("vapi-widget",)),
    Vendor("Retell AI", "voice", ("retellai.com", "retell-client-js-sdk")),
    # Live-chat platforms with optional AI agents
    Vendor("Intercom", "chat", ("widget.intercom.io", "js.intercomcdn.com", "intercomsettings")),
    Vendor("Zendesk", "chat", ("static.zdassets.com", "v2.zopim.com")),
    Vendor("Drift", "chat", ("js.driftt.com",)),
    Vendor("Tidio", "chat", ("code.tidio.co",)),
    Vendor("Crisp", "chat", ("client.crisp.chat",)),
    Vendor("HubSpot", "chat", ("js.usemessages.com", "js.hs-scripts.com")),
    Vendor("Freshchat", "chat", ("wchat.freshchat.com", "fw-cdn.com")),
    Vendor("LiveChat", "chat", ("cdn.livechatinc.com",)),
    Vendor("Tawk.to", "chat", ("embed.tawk.to",)),
    Vendor("Gorgias", "chat", ("config.gorgias.chat",)),
    Vendor("Olark", "chat", ("static.olark.com",)),
    Vendor("Smartsupp", "chat", ("smartsuppchat.com",)),
    Vendor("Userlike", "chat", ("userlike-cdn-widgets",)),
    Vendor("Chatwoot", "chat", ("chatwootsdk", "/packs/js/sdk.js")),
    Vendor("Salesforce Embedded Messaging", "chat", ("embeddedservice", "embedded_svc")),
    Vendor("Genesys", "chat", ("apps.mypurecloud", "genesys-bootstrap")),
)


def detect_vendors(haystack: str, tags: set[str] | None = None) -> list[Vendor]:
    """Return every vendor whose signature appears in the page's script/iframe URLs or inline code."""
    low = haystack.lower()
    tags = {t.lower() for t in (tags or set())}
    found: list[Vendor] = []
    for vendor in VENDORS:
        if any(needle in low for needle in vendor.needles) or any(tag in tags for tag in vendor.tags):
            found.append(vendor)
    return found
