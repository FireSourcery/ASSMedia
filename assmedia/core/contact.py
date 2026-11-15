"""Contact details in text: email addresses and phone-like numbers."""
import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")


def has_contact(text: str) -> bool:
    """True if the text holds an email address or a phone-like number (9+ digits)."""
    if _EMAIL.search(text):
        return True
    return any(phone_like(match.group(0)) for match in _PHONE.finditer(text))


def phone_like(candidate: str) -> bool:
    """A _PHONE match counts when it has 9+ digits and isn't a date-time like 2026-11-10 12."""
    digits = sum(ch.isdigit() for ch in candidate)
    return digits >= 9 and not re.fullmatch(r"\d{4}-\d{2}-\d{2}[\sT]\d{2}", candidate.strip())
