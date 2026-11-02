from importlib import resources

import pytest
import yaml

from mrp import catalog


def _write(tmp_path, change):
    raw = yaml.safe_load(resources.files("mrp.config").joinpath("models.yaml").read_text())
    change(raw)
    p = tmp_path / "models.yaml"
    p.write_text(yaml.safe_dump(raw))
    return str(p)


def test_the_shipped_catalogue_loads():
    assert catalog.load().models


@pytest.mark.parametrize(
    "change,name",
    [
        (lambda r: r["models"]["fast-small"].update(price_in=-0.74), "fast-small"),
        (lambda r: r["models"]["open-8b"].update(price_out=-1), "open-8b"),
        (lambda r: r["models"]["open-70b"].update(context=0), "open-70b"),
        (lambda r: r["quality_targets"].update(standard=90), "standard"),
        (lambda r: r["quality_targets"].update(economy=0), "economy"),
        (lambda r: r["plans"]["team"].update(max_request_cost=-1), "team"),
        (lambda r: r["plans"]["free"].update(markup=-0.1), "free"),
        (lambda r: r["cache"].update(cached_answer_charge=1.5), "cached_answer_charge"),
    ],
)
def test_a_broken_catalogue_is_refused_and_named(tmp_path, change, name):
    path = _write(tmp_path, change)
    with pytest.raises(catalog.CatalogError) as e:
        catalog.load(path)
    assert name in str(e.value)
    assert isinstance(e.value, ValueError)


def test_edge_values_are_valid(tmp_path):
    def change(r):
        r["quality_targets"]["high"] = 1.0
        r["models"]["open-8b"]["price_in"] = 0
        r["cache"]["cached_answer_charge"] = 0

    assert catalog.load(_write(tmp_path, change)).models
