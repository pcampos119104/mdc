"""Pure normalization helpers for legacy member source values."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_FLOOR

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

_DATE_PATTERN = re.compile(
    r"^\s*(?P<day>\d{1,2})\s*[/.-]\s*(?P<month>\d{1,2})"
    r"\s*[/.-]\s*(?P<year>\d{4})\s*$"
)
_ISO_DATE_PATTERN = re.compile(
    r"^\s*(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\s*$"
)

_BRAZILIAN_STATES = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}
_VALID_UFS = frozenset(_BRAZILIAN_STATES.values())


def clean_preserved_text(value: object | None) -> str:
    """Clean surrounding and repeated whitespace while preserving display text."""
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFC", str(value))
    return " ".join(normalized.split())


def comparison_key(value: object | None) -> str:
    """Return an accent, case, punctuation, and whitespace-insensitive key."""
    preserved = clean_preserved_text(value)
    decomposed = unicodedata.normalize("NFKD", preserved)
    key_parts: list[str] = []
    for character in decomposed:
        if unicodedata.combining(character):
            continue
        if character.isalnum():
            key_parts.append(character.casefold())
        else:
            key_parts.append(" ")
    return " ".join("".join(key_parts).split())


def digits_only(value: object | None) -> str:
    """Return only Unicode decimal digits converted to their ASCII form."""
    if value is None:
        return ""

    digits: list[str] = []
    for character in str(value):
        if character.isdecimal():
            digits.append(str(unicodedata.decimal(character)))
    return "".join(digits)


def is_valid_cpf(value: object | None) -> bool:
    """Return whether a CPF has 11 digits and valid check digits."""
    cpf = digits_only(value)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    def check_digit(first_digits: str, weight: int) -> int:
        """Calculate one CPF check digit."""
        total = sum(
            int(digit) * factor
            for digit, factor in zip(first_digits, range(weight, 1, -1))
        )
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    first = check_digit(cpf[:9], 10)
    second = check_digit(cpf[:10], 11)
    return cpf[-2:] == f"{first}{second}"


def normalize_cpf(value: object | None) -> str | None:
    """Return a valid CPF as digits, or ``None`` for blank or invalid input."""
    cpf = digits_only(value)
    return cpf if is_valid_cpf(cpf) else None


def normalize_phone(value: object | None) -> str | None:
    """Return a model-compatible phone representation using digits only."""
    phone = digits_only(value)
    if 8 <= len(phone) <= 15:
        return phone
    return None


def normalize_cep(value: object | None) -> str | None:
    """Return an eight-digit Brazilian postal code, or ``None`` if invalid."""
    postal_code = digits_only(value)
    return postal_code if len(postal_code) == 8 else None


def normalize_email(value: object | None) -> str | None:
    """Return a lower-case Django-valid email, or ``None`` if malformed."""
    email = clean_preserved_text(value)
    if not email:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email.casefold()


def parse_brazilian_date(value: object | None) -> date | None:
    """Parse common unambiguous Brazilian or ISO calendar date forms."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value)
    match = _DATE_PATTERN.fullmatch(text) or _ISO_DATE_PATTERN.fullmatch(text)
    if not match:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None


def excel_serial_to_date(value: object, *, date_1904: bool = False) -> date:
    """Convert a numeric Excel serial to a real calendar date."""
    try:
        serial = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid Excel date serial: {value!r}") from exc

    if not serial.is_finite():
        raise ValueError(f"Invalid Excel date serial: {value!r}")
    whole_days = int(serial.to_integral_value(rounding=ROUND_FLOOR))

    if date_1904:
        if whole_days < 0:
            raise ValueError(f"Invalid Excel 1904 date serial: {value!r}")
        epoch = date(1904, 1, 1)
    else:
        if whole_days <= 0 or whole_days == 60:
            raise ValueError(f"Invalid Excel 1900 date serial: {value!r}")
        epoch = (
            date(1899, 12, 31) if whole_days < 60 else date(1899, 12, 30)
        )

    try:
        return epoch + timedelta(days=whole_days)
    except OverflowError as exc:
        raise ValueError(f"Excel date serial is out of range: {value!r}") from exc


def brazilian_state_to_uf(value: object | None) -> str | None:
    """Return a Brazilian UF for either a state name or existing UF."""
    key = comparison_key(value)
    if not key:
        return None
    uf = key.upper()
    if uf in _VALID_UFS:
        return uf
    return _BRAZILIAN_STATES.get(key)
