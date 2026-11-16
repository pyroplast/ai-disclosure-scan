import io
import json
import subprocess
import sys
from pathlib import Path

from ai_disclosure_scan import mcp_server

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"


def call(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return mcp_server.handle(msg)


def tool(name, **arguments):
    reply = call("tools/call", {"name": name, "arguments": arguments})
    result = reply["result"]
    return result["isError"], result["content"][0]["text"]


def test_initialize_negotiates_version():
    r = call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}})
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert r["result"]["capabilities"]["tools"] == {"listChanged": False}
    r = call("initialize", {"protocolVersion": "1999-01-01"})
    assert r["result"]["protocolVersion"] == mcp_server.SUPPORTED_VERSIONS[0]


def test_notifications_get_no_reply_and_unknown_methods_error():
    assert mcp_server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert call("nope")["error"]["code"] == -32601
    assert call("ping")["result"] == {}


def test_tool_list_has_schemas():
    tools = call("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["scan_page", "scan_transcript", "scan_files", "list_rules"]
    for t in tools:
        assert t["inputSchema"]["type"] == "object" and t["description"]


def test_scan_transcript_text_returns_findings_with_legal_basis():
    is_error, text = tool("scan_transcript", text="User: are you a bot?\nAssistant: Hi! I'm Sarah, a real person.")
    assert not is_error
    report = json.loads(text)
    found = {f["rule_id"] for f in report["results"][0]["findings"]}
    assert "INT-003" in found
    assert report["rules"]["INT-003"]["basis"][0]["pinpoint"] == "Article 50(1), first sentence"


def test_scan_transcript_accepts_json_and_jsonl_text():
    msgs = [{"role": "assistant", "content": "Hello, I'm an AI assistant."}]
    assert json.loads(tool("scan_transcript", text=json.dumps(msgs))[1])["summary"]["pass"] == 1
    jsonl = "\n".join(json.dumps({"id": str(i), "messages": msgs}) for i in range(3))
    assert json.loads(tool("scan_transcript", text=jsonl)[1])["summary"]["scanned"] == 3


def test_scan_files_and_page_on_local_examples():
    _, text = tool("scan_files", paths=[str(EX / "media")], kind="media")
    assert json.loads(text)["summary"]["scanned"] == 4
    _, text = tool("scan_files", paths=["/no/such/file"], kind="transcript")
    assert json.loads(text)["summary"]["errors"] == 1


def test_bad_arguments_are_tool_errors_not_crashes():
    assert tool("scan_page", urls=["not a url"])[0] is True
    assert tool("scan_transcript", text="")[0] is True
    assert tool("scan_files", paths=["x"], kind="pdf")[0] is True
    assert call("tools/call", {"name": "nope", "arguments": {}})["error"]["code"] == -32602


def test_list_rules():
    _, text = tool("list_rules")
    assert any(r["id"] == "BRW-001" for r in json.loads(text))


def test_serve_loop_over_streams():
    lines = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(x) for x in lines) + "\n\nnot json\n")
    stdout = io.StringIO()
    mcp_server.serve(stdin, stdout)
    replies = [json.loads(x) for x in stdout.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, 2, None]
    assert replies[2]["error"]["code"] == -32700


def test_real_subprocess_handshake():
    proc = subprocess.run(
        [sys.executable, "-m", "ai_disclosure_scan", "mcp"],
        input=json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}) + "\n",
        capture_output=True, text=True, timeout=30, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["id"] == 7
