"""UK VAT number normalisation and offline validation.

Offline validation (format + checksum) only says a number COULD exist.
Only HMRC can say it IS registered, and to whom.
"""
import re 

WEIGHTS = (8, 7, 6, 5, 4, 3, 2)

def normalise(raw: str) -> str | None:
    """Return the 9-digit core of a GB VAT number, or None if impossible."""
    if not raw:
        return None
    s = re.sub(r"[\s.\-]", "", raw.upper())
    if s.startswith(("GB", "XI")):
        s = s[2:]
    elif s.endswith(("GB")):
        s = s[:-2]
    return s if re.fullmatch(r"\d{9}", s) else None


def checksum_ok(digits: str) -> bool:
    """mod-97 check: old scheme (total % 97 == 0) or new '9755' scheme."""
    total = sum(int(d) * w for d, w in zip(digits[:7], WEIGHTS)) + int(digits[7:])
    return total % 97 == 0 or (total + 55) % 97 == 0

def validate(raw: str) -> tuple[bool, str]:
    """Return (is_valid, reason); reason in {'ok', 'bad_format', 'bad_checksum'}."""
    digits = normalise(raw)
    if digits is None:
        return False, "bad_format"
    if not checksum_ok(digits):
        return False, "bad_checksum"
    return True, "ok"