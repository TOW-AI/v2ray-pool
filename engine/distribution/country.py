"""Group publishable records by verified egress country."""

from collections import defaultdict


def group_by_country(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        code = record.get("country_code")
        if isinstance(code, str) and len(code) == 2 and code.upper() != "XX":
            grouped[code.upper()].append(record)
    return dict(grouped)
