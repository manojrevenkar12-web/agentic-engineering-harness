import pytest

from mrp.cache import slots


@pytest.mark.parametrize(
    "a,b",
    [
        ("Is the EU plan refundable?", "Is the EU plan not refundable?"),
        ("Does the API have a rate limit?", "Does the API have no rate limit?"),
        ("Will the invoice be sent on Friday?", "Will the invoice never be sent on Friday?"),
        ("Is the EU plan refundable?", "Isn't the EU plan refundable?"),
        ("Can I export my data?", "I can't export my data?"),
    ],
)
def test_a_question_and_its_negation_are_different_requests(a, b):
    assert slots(a) != slots(b)


@pytest.mark.parametrize(
    "a,b",
    [
        ("Hi, what is the refund limit for EU customers?", "what is the refund limit for EU customers"),
        ("Please tell me: is the EU plan refundable?", "Is the EU plan refundable?"),
        ("Is the EU plan NOT refundable?", "is the eu plan not refundable"),
        ("Isn't the EU plan refundable?", "Is not the EU plan refundable?"),
    ],
)
def test_repeats_still_match(a, b):
    assert slots(a) == slots(b)
