"""Group publishable records by parsed protocol."""

from collections import defaultdict


def group_by_protocol(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        protocol = record.get("protocol")
        if protocol in {"vless", "vmess", "trojan", "ss"}:
            grouped[protocol].append(record)
    return dict(grouped)
