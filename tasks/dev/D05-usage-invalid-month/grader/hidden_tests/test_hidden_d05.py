import pytest

from tests.conftest import chat


@pytest.mark.parametrize("month", ["2026-13", "26-01", "january", "", "2026-1-1", "2026-00"])
async def test_a_malformed_month_is_a_422(env, month):
    _, h = await env.workspace()
    r = await env.client.get("/v1/usage", params={"month": month}, headers=h)
    assert r.status_code == 422, r.text
    assert "YYYY-MM" in r.text


async def test_a_valid_month_still_reports(env):
    _, h = await env.workspace()
    r = await env.client.post("/v1/chat/completions", json=chat("Summarize the key points of our Q3 call."), headers=h)
    assert r.status_code == 200
    import time

    month = time.strftime("%Y-%m", time.gmtime())
    rep = await env.client.get("/v1/usage", params={"month": month}, headers=h)
    assert rep.status_code == 200, rep.text
    assert rep.json()["lines"]
