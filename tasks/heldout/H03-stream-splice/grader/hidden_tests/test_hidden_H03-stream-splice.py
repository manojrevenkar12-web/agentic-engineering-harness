"""Hidden tests for H03: never splice another model into a stream that has started."""

import json

import pytest

from mrp.providers.base import Delta, ProviderError
from tests.conftest import chat


def broken_stream(after_chunks: int):
    async def stream(upstream, messages, max_tokens, request_id, api_key=None):
        for i in range(after_chunks):
            yield Delta(f"part {i} of an answer ")
        raise ProviderError("upstream connection reset", retryable=True)

    return stream


def events(text: str) -> list:
    return [line[6:] for line in text.splitlines() if line.startswith("data: ")]


BODY = chat(
    "Tell me about the history of Berlin.",
    stream=True,
    model="frontier-mid",
    mrp={"fallbacks": ["general-b", "open-70b"]},
)


@pytest.mark.parametrize("chunks", [1, 3])
async def test_a_failure_after_the_first_chunk_ends_the_stream_with_an_error(env, monkeypatch, chunks):
    ws, h = await env.workspace()
    monkeypatch.setattr(env.providers["closed-a"], "stream", broken_stream(chunks))
    r = await env.client.post("/v1/chat/completions", json=BODY, headers=h)
    assert r.status_code == 200
    ev = events(r.text)
    assert "[DONE]" not in ev
    parsed = [json.loads(e) for e in ev]
    content = [e for e in parsed if "choices" in e]
    assert len(content) == chunks and {e["model"] for e in content} == {"frontier-mid"}
    assert parsed[-1]["error"]["type"] == "provider_error"
    assert "upstream connection reset" in parsed[-1]["error"]["message"]
    assert [e for e in parsed if "error" in e] == [parsed[-1]]
    assert env.providers["closed-b"].calls == 0 and env.providers["self-hosted"].calls == 0
    async with env.db.tenant(ws) as conn:
        assert await conn.fetchval("SELECT status FROM mrp.usage") == "cancelled"
        calls = await conn.fetch("SELECT model FROM mrp.provider_calls")
    assert [c["model"] for c in calls] == ["frontier-mid"]


async def test_a_failure_before_the_first_chunk_still_falls_back(env, monkeypatch):
    ws, h = await env.workspace()
    monkeypatch.setattr(env.providers["closed-a"], "stream", broken_stream(0))
    r = await env.client.post("/v1/chat/completions", json=BODY, headers=h)
    ev = events(r.text)
    assert ev[-1] == "[DONE]"
    content = [json.loads(e) for e in ev[:-1]]
    assert content and {e["model"] for e in content} == {"general-b"}
    assert not any("error" in e for e in content)
    async with env.db.tenant(ws) as conn:
        assert await conn.fetchval("SELECT status FROM mrp.usage") == "ok"
        calls = await conn.fetch("SELECT model, status, delivered FROM mrp.provider_calls ORDER BY created_at")
    assert [(c["model"], c["status"], c["delivered"]) for c in calls] == [
        ("frontier-mid", "failed", False),
        ("general-b", "ok", True),
    ]
