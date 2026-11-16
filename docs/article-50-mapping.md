# How each check maps to Article 50

Generated from the rule catalogue (`ai-disclosure-scan rules --format md`). Do not edit by hand.

Every check lists the exact place in its source and a paraphrase of what that place says, so you can open the source and compare. Only sources marked **law** bind. The line *Scanner's reading* is this project's own step from the provision to something a script can observe; it is an interpretation, not the law.

## Sources

| Weight | Source |
|---|---|
| law | [Regulation (EU) 2024/1689 (AI Act), Article 50, consolidated text of 27 July 2026 (European Commission, AI Act Service Desk)](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50) |
| official guidance | [European Commission, FAQ: Transparency obligations under Article 50 of the AI Act](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act) |
| official guidance | [European Commission, Guidelines on the implementation of the transparency obligations applicable to certain AI systems (Article 50 AI Act), 20 July 2026](https://digital-strategy.ec.europa.eu/en/library/guidelines-transparency-obligations-providers-and-deployers-ai-systems) |
| voluntary code | [European Commission, Code of Practice on marking and labelling of AI-generated content, 10 June 2026](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content) |
| secondary summary | [William Fry, 'Time Running Out as AI Transparency Guidelines Published' (a law firm's summary of the Commission Guidelines)](https://www.williamfry.com/knowledge/time-running-out-as-ai-transparency-guidelines-published/) |

The official journal text of the Act is at <https://eur-lex.europa.eu/eli/reg/2024/1689/oj>. Article 50 has applied since 2 August 2026.

## Checks

### INT-001: No AI disclosure anywhere in the conversation

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'When do providers of AI systems have to inform people they are interacting with an AI system?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Notice has to be given from the start of the first interaction, clearly and distinguishably. The 'obvious' exception is judged from the view of an average, reasonably well-informed person and is to be interpreted restrictively.

**Scanner's reading:** The scanner searches every assistant message for an explicit AI term (AI, bot, chatbot, artificial intelligence and equivalents in eight languages). Finding none, it reports that the transcript holds no disclosure. It cannot see a notice shown by the chat UI outside the message stream, and it does not judge whether the 'obvious' exception applies.

**Usual fix:** Have the assistant say it is an AI in its first message, or show a clear, visible AI notice in the chat UI before the first reply (then scan with --ui-notice).

### INT-002: AI disclosure arrives after the first reply

Article 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'When do providers of AI systems have to inform people they are interacting with an AI system?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Notice has to be given from the start of the first interaction, clearly and distinguishably. The 'obvious' exception is judged from the view of an average, reasonably well-informed person and is to be interpreted restrictively.

**Scanner's reading:** The scanner treats the assistant's first message as the first interaction. A disclosure that first appears in a later message is reported as late.

**Usual fix:** Move the disclosure into the greeting or the first reply.

### INT-003: Assistant claims to be human or denies being an AI

Article 50(1) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.

**Scanner's reading:** Article 50 does not mention impersonation in so many words. The scanner reads a statement such as 'I'm a real person' or 'I'm not a bot' as incompatible with informing people that they are interacting with an AI system.

**Usual fix:** Remove human-claim instructions from the prompt and add a rule that the assistant always confirms it is an AI when asked.

### INT-004: Asked whether it is a bot, the assistant does not give a clear answer

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.

**Scanner's reading:** Article 50 contains no rule about answering direct questions. The scanner treats a direct question about AI status that gets no explicit answer as a sign the person was not informed in a clear manner.

**Usual fix:** Add a tested behaviour: any 'are you a bot / a human?' question gets a plain 'I'm an AI' answer.

### INT-005: Only a generic label such as 'virtual assistant' is used

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *secondary summary* · [Section on Article 50(1) and AI agents](https://www.williamfry.com/knowledge/time-running-out-as-ai-transparency-guidelines-published/): Reports that, under the Commission Guidelines, generic references to an 'assistant', disclosures buried in terms and conditions, and machine-readable marks users cannot perceive are each insufficient on their own. Not verified against the Guidelines text by this project: check the Guidelines before relying on it.

**Scanner's reading:** The scanner separates explicit AI terms from generic labels (virtual, digital or smart assistant). A conversation with only a generic label is flagged for a person to judge, not as a gap, because the point rests on a secondary summary of the Guidelines.

**Usual fix:** Say 'AI' (or the local-language equivalent) in plain words: 'I'm an AI assistant'.

### INT-010: AI disclosure present at the first interaction

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.

**Scanner's reading:** The assistant's first message contains an explicit AI term. The scanner does not judge prominence, wording quality or accessibility.

**Usual fix:** Nothing to fix. Keep a regression test so it stays that way.

### PAGE-001: Chat or voice widget found, no AI wording in the page

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'When do providers of AI systems have to inform people they are interacting with an AI system?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Notice has to be given from the start of the first interaction, clearly and distinguishably. The 'obvious' exception is judged from the view of an average, reasonably well-informed person and is to be interpreted restrictively.

**Scanner's reading:** The scanner recognises the widget by its script signature and searches the HTML the server sends for AI wording. It does not run JavaScript or open the widget, so a notice shown inside the widget is invisible to it. That is why page findings about chat are REVIEW, never GAP. A widget from a live-chat platform may also be staffed by people only.

**Usual fix:** Open the widget and check its first message, or export a conversation and run the transcript scan. Add a visible AI notice next to the launcher if there is none.

### PAGE-002: AI is mentioned on the page, but not as a clear notice about the chat

Article 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.

**Scanner's reading:** The scanner recognises the widget by its script signature and searches the HTML the server sends for AI wording. It does not run JavaScript or open the widget, so a notice shown inside the widget is invisible to it. That is why page findings about chat are REVIEW, never GAP. It distinguishes a sentence about the chat ('you're chatting with our AI assistant') from AI wording elsewhere on the page.

**Usual fix:** Add a short notice tied to the chat itself, for example 'You're chatting with our AI assistant'.

### PAGE-003: Clear AI notice for the chat found

Article 50(1), 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *law* · [Article 50(5), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information must conform to the applicable accessibility requirements.

**Scanner's reading:** The page's visible text, or the widget's inline configuration, contains a sentence that tells visitors the chat is an AI. The scanner does not check where on the screen it appears.

**Usual fix:** Nothing to fix. Confirm the notice is also visible on mobile and to screen readers.

### PAGE-004: AI wording exists only where visitors cannot see it

Article 50(5) · duty holder: provider

**Basis**

- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *law* · [Article 50(5), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information must conform to the applicable accessibility requirements.
- *secondary summary* · [Section on Article 50(1) and AI agents](https://www.williamfry.com/knowledge/time-running-out-as-ai-transparency-guidelines-published/): Reports that, under the Commission Guidelines, generic references to an 'assistant', disclosures buried in terms and conditions, and machine-readable marks users cannot perceive are each insufficient on their own. Not verified against the Guidelines text by this project: check the Guidelines before relying on it.

**Scanner's reading:** The scanner separates visible text from hidden elements (display:none, aria-hidden, screen-reader-only classes), attribute text (alt, title, aria-label) and metadata. Screen-reader-only text does serve some users, so this is for a person to judge.

**Usual fix:** Put the notice in visible text near the chat launcher.

### PAGE-005: No chat or voice widget recognised

Article 50(1) · duty holder: provider

**Basis**

- *law* · [Article 50(1), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers must design and develop AI systems meant to interact directly with people so that those people are informed they are interacting with an AI system, unless this is obvious to a reasonably well-informed, observant and circumspect person in the circumstances and context of use.

**Scanner's reading:** Absence of a known signature says nothing about whether Article 50(1) applies to the site.

**Usual fix:** If the page does have a chat, export a conversation and run the transcript scan.

### MED-001: AI-generator traces, but no standard machine-readable AI marking in the metadata

Article 50(2) · duty holder: provider

**Basis**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.
- *law* · [Article 50(2), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The technical solutions must be effective, interoperable, robust and reliable as far as technically feasible, considering the type of content, implementation costs and the generally acknowledged state of the art.
- *law* · [Article 50(2), third sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The duty does not apply where the system only assists with standard editing, does not substantially alter the input data or its semantics, or is authorised by law for criminal-offence purposes.
- *official guidance* · [Question 'When do providers of AI systems have to mark the outputs of their generative AI systems and ensure their detectability?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Systems placed on the market before 2 August 2026 have a grace period for the marking and detection duty only, and must comply from 2 December 2026. The FAQ names no specific technique and points to the Code of Practice as one way to demonstrate compliance.
- *voluntary code* · [Section 1 (providers): marking and detection](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content): A voluntary code. Signatories who follow it can rely on its measures to demonstrate compliance; others must show their own measures are adequate.

**Scanner's reading:** The duty sits with the provider of the generating system, not with whoever hosts the file, and the Act names no specific standard. The scanner reads two interoperable metadata markings: a C2PA manifest that declares an AI source type, and the IPTC Digital Source Type. 'Gap' here means neither was found. It does not rule out an invisible watermark, which only the vendor's detector can read, and it does not test the exceptions or the transition period.

**Usual fix:** Enable Content Credentials (C2PA) or IPTC Digital Source Type marking in the generating system, and check that your CMS or CDN does not strip metadata on upload or resize.

### MED-002: Standard machine-readable AI marking present

Article 50(2) · duty holder: provider

**Basis**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.
- *law* · [Article 50(2), second sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The technical solutions must be effective, interoperable, robust and reliable as far as technically feasible, considering the type of content, implementation costs and the generally acknowledged state of the art.
- *voluntary code* · [Section 1 (providers): marking and detection](https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content): A voluntary code. Signatories who follow it can rely on its measures to demonstrate compliance; others must show their own measures are adequate.

**Scanner's reading:** The scanner found a C2PA manifest with an AI source type or an IPTC Digital Source Type of trainedAlgorithmicMedia / compositeWithTrainedAlgorithmicMedia. It does not verify the manifest's signature and does not test robustness.

**Usual fix:** Nothing to fix. Metadata is one layer and is easily stripped; check it survives your publishing pipeline.

### MED-003: Provenance manifest present, AI origin not stated

Article 50(2) · duty holder: provider

**Basis**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.

**Scanner's reading:** The scanner cannot tell whether the file is AI-made. It reports the manifest as context.

**Usual fix:** Nothing to fix unless the file was in fact AI-generated.

### MED-004: No provenance signal in the file

Article 50(2) · duty holder: provider

**Basis**

- *law* · [Article 50(2), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Providers of AI systems that generate synthetic audio, image, video or text must ensure the outputs are marked in a machine-readable format and detectable as artificially generated or manipulated.

**Scanner's reading:** No C2PA manifest, no IPTC Digital Source Type and no generator traces. Invisible watermarks are not checked. This is context, not a finding against anyone.

**Usual fix:** If this file came out of a generative system, its metadata marking is missing or was stripped.

### LBL-001: AI-made media on the page, no visible AI label

Article 50(4), 50(5) · duty holder: deployer

**Basis**

- *law* · [Article 50(4), first subparagraph, first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Deployers of an AI system that generates or manipulates image, audio or video content constituting a deep fake must disclose that the content has been artificially generated or manipulated.
- *law* · [Article 50(4), first subparagraph, third sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): For evidently artistic, creative, satirical, fictional or similar works, the duty is limited to disclosing the existence of such content in a way that does not hamper the display or enjoyment of the work.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'What is a deepfake and when do they need to be labelled?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): The disclosure must be perceivable, for example through visible or audible labels, without specific tools or dedicated actions. Deployers cannot rely on the provider's embedded machine-readable marking to meet this duty.

**Scanner's reading:** The scanner sees that media on the page is AI-made (by its marking or generator traces) and that the page's visible text has no AI label. It cannot judge whether the media is a deep fake as defined in Article 3(60), which is the condition for the duty, or whether the artistic exception applies.

**Usual fix:** If the media depicts real-looking people, places or events, add a visible label (the Commission publishes EU icons for this).

### LBL-002: AI-made media on the page, visible AI label found

Article 50(4), 50(5) · duty holder: deployer

**Basis**

- *law* · [Article 50(4), first subparagraph, first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Deployers of an AI system that generates or manipulates image, audio or video content constituting a deep fake must disclose that the content has been artificially generated or manipulated.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'What is a deepfake and when do they need to be labelled?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): The disclosure must be perceivable, for example through visible or audible labels, without specific tools or dedicated actions. Deployers cannot rely on the provider's embedded machine-readable marking to meet this duty.

**Scanner's reading:** The scanner found an AI label somewhere in the page's visible text. It does not check that the label is placed next to the media.

**Usual fix:** Nothing to fix. Check the label sits next to the media it refers to.

### LBL-003: Page is declared AI-generated in metadata only

Article 50(4), 50(5) · duty holder: deployer

**Basis**

- *law* · [Article 50(4), second subparagraph](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): Deployers of an AI system that generates or manipulates text published to inform the public on matters of public interest must disclose that the text has been artificially generated or manipulated. This does not apply where the content has undergone human review or editorial control and a natural or legal person holds editorial responsibility for its publication.
- *law* · [Article 50(5), first sentence](https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50): The information required by paragraphs 1 to 4 must be given to the people concerned in a clear and distinguishable manner, at the latest at the time of the first interaction or exposure.
- *official guidance* · [Question 'What constitutes the human review or editorial control/responsibility required to qualify for an exemption from the labelling obligation?'](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act): Human review means substantive examination by people with relevant expertise; spell-checking and grammar correction do not count. Editorial responsibility means a person holds ultimate legal responsibility for the publication.

**Scanner's reading:** The scanner found a machine-readable declaration (a meta tag, a data-ai attribute or a JSON-LD digitalSourceType) and no visible AI label. Whether the text informs the public on a matter of public interest, and whether it had human editorial review, are for a person to establish.

**Usual fix:** Add a visible notice, or document the editorial review that makes the exception apply.

