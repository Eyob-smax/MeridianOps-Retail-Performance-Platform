import re
from collections.abc import Mapping

MASK_PATTERN = re.compile(r"(^..).+(.{2}$)")


def mask_sensitive(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return MASK_PATTERN.sub(r"\1***\2", value)


def mask_record(record: Mapping[str, str | int | float | None], sensitive_keys: set[str]) -> dict[str, str | int | float | None]:
    masked: dict[str, str | int | float | None] = {}
    for key, value in record.items():
        if key in sensitive_keys and isinstance(value, str):
            masked[key] = mask_sensitive(value)
        else:
            masked[key] = value
    return masked
