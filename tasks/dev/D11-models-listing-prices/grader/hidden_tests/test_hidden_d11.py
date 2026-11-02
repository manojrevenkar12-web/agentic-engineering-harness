from decimal import Decimal

from mrp.catalog import load


async def test_models_show_context_and_prices(env):
    _, h = await env.workspace()
    data = (await env.client.get("/v1/models", headers=h)).json()["data"]
    by_id = {d["id"]: d for d in data}
    assert by_id["auto"] == {"id": "auto", "object": "model", "owned_by": "router"}
    for m in load().models.values():
        d = by_id[m.id]
        assert d["context"] == m.context and isinstance(d["context"], int)
        assert Decimal(str(d["price_in"])) == m.price_in
        assert Decimal(str(d["price_out"])) == m.price_out
        assert d["open_weight"] == m.open_weight


async def test_fine_tuned_for_only_where_set(env):
    _, h = await env.workspace()
    data = {d["id"]: d for d in (await env.client.get("/v1/models", headers=h)).json()["data"]}
    assert data["open-8b-extract"]["fine_tuned_for"] == "extraction"
    assert "fine_tuned_for" not in data["open-8b"]
