import pytest

from mrp.agents import needs_approval


@pytest.mark.parametrize(
    "to",
    [
        ["someone@notexample.com"],
        ["someone@example.com.attacker.net"],
        ["someone@sub.example.com"],
        ["x@example.com", "y@other.org"],
        ["y@other.org", "x@example.com"],
        ["no-at-sign-example.com"],
    ],
)
def test_external_or_lookalike_recipients_need_approval(to):
    assert needs_approval("gmail.send", {"to": to})


@pytest.mark.parametrize("to", [["a@example.com"], ["Bob@EXAMPLE.com"], ["a@example.com", "b@Example.Com"]])
def test_internal_recipients_do_not(to):
    assert not needs_approval("gmail.send", {"to": to})


def test_other_internal_domains():
    assert not needs_approval("gmail.send", {"to": ["x@corp.test"]}, internal_domains=("corp.test", "example.com"))
    assert needs_approval("gmail.send", {"to": ["x@corp.test.evil"]}, internal_domains=("corp.test",))
