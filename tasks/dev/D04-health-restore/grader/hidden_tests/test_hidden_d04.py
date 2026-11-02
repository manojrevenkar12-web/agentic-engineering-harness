from mrp.health import Health
from mrp.router import QualityTable


def _health() -> Health:
    t = QualityTable()
    for _ in range(2000):
        t.record("extraction", "m", True, check_passed=True)
    return Health(t)


def _break(h: Health) -> None:
    for _ in range(h.window):
        if h.observe("extraction", "m", False):
            return
    raise AssertionError("a model failing every answer was never excluded")


def test_a_restored_model_is_not_excluded_by_the_next_answer():
    h = _health()
    _break(h)
    assert "m" in h.excluded("extraction")
    h.restore("extraction", "m")
    assert "m" not in h.excluded("extraction")
    for _ in range(h.min_samples - 1):
        assert not h.observe("extraction", "m", True)
    assert "m" not in h.excluded("extraction")


def test_a_restored_model_needs_new_samples_before_it_can_be_excluded():
    h = _health()
    _break(h)
    h.restore("extraction", "m")
    for _ in range(h.min_samples - 1):
        assert not h.observe("extraction", "m", False)
    assert "m" not in h.excluded("extraction")


def test_a_restored_model_that_is_still_bad_is_excluded_again():
    h = _health()
    _break(h)
    h.restore("extraction", "m")
    _break(h)
    assert "m" in h.excluded("extraction")
