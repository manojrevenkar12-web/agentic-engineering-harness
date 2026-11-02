from mrp.catalog import load
from tests.conftest import chat

OPEN = {m.id for m in load().models.values() if m.open_weight}


async def test_auto_routing_uses_only_open_weight_models(env):
    _, h = await env.workspace()
    for prompt in ("Summarize the key points of our Q3 call.", "Extract the invoice number as JSON: INV-7", "hello there"):
        r = await env.client.post("/v1/chat/completions", json=chat(prompt, mrp={"open_weight_only": True}), headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["model"] in OPEN


async def test_a_named_closed_model_is_refused(env):
    _, h = await env.workspace()
    r = await env.client.post(
        "/v1/chat/completions", json=chat("hello", model="frontier-mid", mrp={"open_weight_only": True}), headers=h
    )
    assert r.status_code == 422, r.text
    assert "open" in r.text.lower()


async def test_a_named_open_model_is_served(env):
    _, h = await env.workspace()
    r = await env.client.post("/v1/chat/completions", json=chat("hello", model="open-70b", mrp={"open_weight_only": True}), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "open-70b"


async def test_no_open_model_can_take_it_means_no_route(env):
    _, h = await env.workspace()
    body = chat("Summarize the key points of our Q3 call.", max_tokens=65_000)
    assert (await env.client.post("/v1/chat/completions", json=body, headers=h)).status_code == 200
    r = await env.client.post("/v1/chat/completions", json={**body, "mrp": {"open_weight_only": True}}, headers=h)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["type"] == "no_route"


async def test_without_the_option_nothing_changes(env):
    _, h = await env.workspace()
    r = await env.client.post("/v1/chat/completions", json=chat("hello", model="frontier-mid"), headers=h)
    assert r.status_code == 200, r.text


async def test_a_cached_answer_from_a_closed_model_is_not_served(env):
    _, h = await env.workspace()
    prompt = "Summarize the key points of our Q3 call."
    first = await env.client.post("/v1/chat/completions", json=chat(prompt, model="frontier-mid"), headers=h)
    assert first.status_code == 200 and first.json()["model"] == "frontier-mid"
    r = await env.client.post("/v1/chat/completions", json=chat(prompt, mrp={"open_weight_only": True}), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["model"] in OPEN
