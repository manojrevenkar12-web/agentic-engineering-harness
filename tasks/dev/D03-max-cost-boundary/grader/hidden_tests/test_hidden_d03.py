from decimal import Decimal

import pytest

from mrp.catalog import load
from mrp.router import NoRoute, QualityTable, decide


def _table() -> QualityTable:
    t = QualityTable()
    for m in load().models:
        for _ in range(400):
            t.record("chat", m, True)
    return t


def test_a_request_costing_exactly_the_limit_is_allowed():
    cat = load()
    cheapest = min(cat.models.values(), key=lambda m: m.cost(1000, 500))
    limit = cheapest.cost(1000, 500)
    route = decide(cat, _table(), "chat", 0.5, 1000, 500, limit)
    assert route.primary.id == cheapest.id


def test_a_request_costing_more_than_the_limit_is_refused():
    cat = load()
    cheapest = min(cat.models.values(), key=lambda m: m.cost(1000, 500))
    with pytest.raises(NoRoute):
        decide(cat, _table(), "chat", 0.5, 1000, 500, cheapest.cost(1000, 500) - Decimal("0.00000001"))


def test_only_models_within_the_limit_are_considered():
    cat = load()
    limit = cat.models["general-b-mini"].cost(2000, 1000)
    route = decide(cat, _table(), "chat", 0.5, 2000, 1000, limit)
    for m in [route.primary, *route.fallbacks]:
        assert m.cost(2000, 1000) <= limit
