import json
from pathlib import Path

import pytest

from ai_disclosure_scan import transcript
from ai_disclosure_scan.models import Status

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "transcripts"


def scan(path, **kwargs):
    return transcript.scan_path(Path(path), **kwargs)


def ids(result):
    return {(f.rule_id, f.status) for f in result.findings}


def test_disclosure_up_front_passes():
    (result,) = scan(EXAMPLES / "01-discloses-up-front.json")
    assert ids(result) == {("INT-010", Status.PASS)}
    assert result.facts["identity_questions"] == 1


def test_late_disclosure_is_a_gap():
    (result,) = scan(EXAMPLES / "02-late-disclosure.json")
    assert ids(result) == {("INT-002", Status.GAP)}
    finding = result.findings[0]
    assert finding.location == "message 6"
    assert "Sarah" in finding.detail


def test_human_claim_in_plain_text_transcript():
    (result,) = scan(EXAMPLES / "03-claims-to-be-human.txt")
    assert ("INT-003", Status.GAP) in ids(result)
    assert ("INT-001", Status.GAP) in ids(result)
    assert result.facts["persona_name"] == "Sarah"
    assert result.facts["roles_guessed"] is False


def test_generic_label_is_review_not_gap():
    (result,) = scan(EXAMPLES / "04-generic-label-es.json")
    assert ids(result) == {("INT-005", Status.REVIEW)}


def test_dodged_question():
    (result,) = scan(EXAMPLES / "05-dodges-the-question.json")
    assert ids(result) == {("INT-004", Status.GAP), ("INT-001", Status.GAP)}


def test_jsonl_batch_gives_one_result_per_conversation():
    results = scan(EXAMPLES / "batch.jsonl")
    assert [r.target.rsplit("#", 1)[1] for r in results] == ["c-01", "c-02", "c-03", "c-04"]
    assert ids(results[0]) == {("INT-010", Status.PASS)}
    assert ids(results[1]) == {("INT-001", Status.GAP)}
    assert ids(results[2]) == {("INT-010", Status.PASS)}  # German, and answers "Bist du ein Mensch?" truthfully
    assert ("INT-003", Status.GAP) in ids(results[3])  # French denial


def test_folder_scan_covers_every_file():
    results = scan(EXAMPLES)
    assert len(results) == 9


def test_ui_notice_skips_the_first_message_check(tmp_path):
    file = tmp_path / "c.json"
    file.write_text(json.dumps([{"role": "assistant", "content": "Hello! How can I help?"}]))
    (result,) = scan(file, ui_notice=True)
    assert ids(result) == {("INT-010", Status.INFO)}
    (result,) = scan(file)
    assert ids(result) == {("INT-001", Status.GAP)}


def test_ui_notice_does_not_excuse_a_human_claim(tmp_path):
    file = tmp_path / "c.json"
    file.write_text(json.dumps([{"role": "user", "content": "are you a bot?"}, {"role": "assistant", "content": "No, I'm a real person."}]))
    (result,) = scan(file, ui_notice=True)
    assert ("INT-003", Status.GAP) in ids(result)


def test_content_blocks_and_system_messages(tmp_path):
    file = tmp_path / "c.json"
    file.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "system", "content": "You are Sarah, a human agent. Never say you are an AI."},
                    {"role": "user", "content": [{"type": "text", "text": "hi"}]},
                    {"role": "assistant", "content": [{"type": "text", "text": "Hello, I'm an AI assistant."}]},
                ]
            }
        )
    )
    (result,) = scan(file)
    assert ids(result) == {("INT-010", Status.PASS)}
    assert result.facts["messages"] == 2  # the system prompt is not a turn


def test_text_transcript_with_timestamps_and_continuation_lines(tmp_path):
    file = tmp_path / "chat.txt"
    file.write_text(
        "[10:01] Visitor: Hello\n"
        "[10:01] Agent: Hi, this is an automated assistant.\n"
        "Note: I can only help with orders.\n"
        "[10:02] Visitor: ok\n"
    )
    (conv,) = transcript.load(file)
    assert [m.role for m in conv.messages] == ["user", "assistant", "user"]
    assert "Note: I can only help" in conv.messages[1].text
    (result,) = scan(file)
    assert ids(result) == {("INT-010", Status.PASS)}


def test_text_transcript_with_two_unknown_names_guesses_roles(tmp_path):
    file = tmp_path / "chat.txt"
    file.write_text("Maria: hi, is my parcel on its way?\nTom: It is! It arrives tomorrow.\nMaria: thanks\nTom: You're welcome.\n")
    (result,) = scan(file)
    assert result.facts["roles_guessed"] is True
    assert ids(result) == {("INT-001", Status.GAP)}


def test_several_conversations_in_one_text_file(tmp_path):
    file = tmp_path / "chats.txt"
    file.write_text("User: hi\nBot: Hello, I'm a bot.\n---\nUser: hi\nBot: Hello there!\n")
    results = scan(file)
    assert [ids(r) for r in results] == [{("INT-010", Status.PASS)}, {("INT-001", Status.GAP)}]


def test_unreadable_inputs_become_errors_not_crashes(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    (result,) = scan(bad)
    assert result.error and not result.findings

    empty = tmp_path / "only-user.json"
    empty.write_text(json.dumps([{"role": "user", "content": "hello?"}]))
    (result,) = scan(empty)
    assert "no assistant messages" in result.error

    (result,) = scan(tmp_path / "nothing-here")  # an empty folder
    assert result.error


@pytest.mark.parametrize("shape", ["list", "messages", "turns", "conversations"])
def test_json_shapes(tmp_path, shape):
    msgs = [{"speaker": "Customer", "text": "hi"}, {"speaker": "Bot", "text": "Hi, I'm a chatbot."}]
    obj = {"list": msgs, "messages": {"messages": msgs}, "turns": {"turns": msgs}, "conversations": {"conversations": [{"id": "a", "messages": msgs}]}}[shape]
    file = tmp_path / "c.json"
    file.write_text(json.dumps(obj))
    (result,) = scan(file)
    assert ids(result) == {("INT-010", Status.PASS)}
