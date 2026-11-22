import pytest
from src.vat import normalise, checksum_ok, validate

# Fill with numbers YOU confirmed on gov.uk/check-uk-vat-number
REAL_NUMBERS = ["660 4548 36", "GB787440102", "GB 226659933", "173140925GB"]

def make_valid(prefix7: str, offset: int) -> str:
    """Build a checksum-valid number for a 7-digit prefix (offset 0 or 55)."""
    total = sum(int(d) * w for d, w in zip(prefix7, (8, 7, 6, 5, 4, 3, 2)))
    for check in range(100):
        if (total + check + offset) % 97 == 0:
            return prefix7 + f"{check:02d}"
    raise ValueError


def test_normalise_variants():
    for raw in ["GB 123 4567 89", "gb123456789", "GB-123-456-789",
                "123456789", "GB123.456.789", "XI123456789"]:
        assert normalise(raw) == "123456789"


def test_normalise_rejects():
    for raw in ["", "GB12345678", "GB1234567890", "GB12345678A", "FR123456789"]:
        assert normalise(raw) is None


@pytest.mark.parametrize("offset", [0, 55])
def test_both_schemes_pass(offset):
    assert checksum_ok(make_valid("1234567", offset))


def test_single_digit_change_fails():
    good = make_valid("2457193", 0)
    # a typo can, rarely, land on the other scheme, so measure the catch rate
    caught = sum(
        not checksum_ok(good[:i] + d + good[i + 1:])
        for i in range(9) for d in "0123456789" if d != good[i]
    )
    assert caught / 81 > 0.95


def test_validate_reasons():
    assert validate("hello") == (False, "bad_format")
    assert validate(make_valid("1234567", 0))[0]


@pytest.mark.parametrize("raw", REAL_NUMBERS)
def test_real_numbers_pass(raw):
    assert validate(raw) == (True, "ok")