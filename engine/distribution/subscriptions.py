"""Generate deterministic subscription files."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any


def encode_uris(uris: list[str], encoding: str) -> bytes:
    unique = list(dict.fromkeys(uri for uri in uris if uri))
    if not unique:
        return b""
    raw = ("\n".join(unique) + "\n").encode("utf-8")
    if encoding == "base64":
        return base64.b64encode(raw)
    if encoding == "plain":
        return raw
    raise ValueError("Subscription encoding must be base64 or plain.")


def write_subscriptions(
    root: Path,
    configs: dict[str, dict[str, Any]],
    rankings: dict[str, list[dict]],
    settings: dict[str, Any],
) -> dict[str, int]:
    sub_root = root / "sub"
    sub_root.mkdir(parents=True, exist_ok=True)
    encoding = settings["encoding"]
    eligible_statuses = {"FIXED_CANDIDATE", "FIXED_VERIFIED", "ROTATING"}
    eligible = [
        item for item in configs.values()
        if item.get("public_redistribution") is True
        and item.get("uri")
        and item.get("status") in eligible_statuses
    ]

    def ordered(items: list[dict]) -> list[str]:
        return [item["uri"] for item in items if item.get("uri")]

    by_status = {name: [item for item in eligible if item.get("status") == name] for name in (
        "FIXED_CANDIDATE", "FIXED_VERIFIED", "ROTATING", "UNSTABLE", "IP_UNVERIFIED", "TESTED"
    )}
    fixed = by_status["FIXED_VERIFIED"] + by_status["FIXED_CANDIDATE"]
    main_statuses = {"FIXED_CANDIDATE", "FIXED_VERIFIED", "TESTED"}
    if settings.get("include_rotating_in_main", False):
        main_statuses.add("ROTATING")
    if settings.get("include_unstable_in_main", False):
        main_statuses.update({"UNSTABLE", "IP_UNVERIFIED"})
    main = [item for item in eligible if item.get("status") in main_statuses]

    def ranked_configs(name: str) -> list[dict]:
        result = []
        for rank in rankings.get(name, []):
            record = configs.get(rank["config_id"])
            if record and record.get("public_redistribution") is True and record.get("uri"):
                result.append(record)
        return result

    balanced_order = {item["config_id"]: index for index, item in enumerate(rankings.get("balanced", []))}
    main.sort(key=lambda item: (balanced_order.get(item["config_id"], 10**9), item["config_id"]))
    outputs: dict[str, list[str]] = {
        "main.txt": ordered(main),
        "fixed.txt": ordered(sorted(fixed, key=lambda item: item["config_id"])),
        "fixed-verified.txt": ordered(sorted(by_status["FIXED_VERIFIED"], key=lambda item: item["config_id"])),
        "fixed-top50.txt": ordered(ranked_configs("fixed")[: int(settings["max_top_configs"])]),
        "rotating.txt": ordered(by_status["ROTATING"]),
        "rotating-top50.txt": ordered(ranked_configs("rotating")[: int(settings["max_top_configs"])]),
        "fastest.txt": ordered(ranked_configs("fastest")),
        "balanced.txt": ordered(ranked_configs("balanced")),
    }
    for filename, uris in outputs.items():
        (sub_root / filename).write_bytes(encode_uris(uris, encoding))

    country_dir = sub_root / "country"
    protocol_dir = sub_root / "protocol"
    country_dir.mkdir(parents=True, exist_ok=True)
    protocol_dir.mkdir(parents=True, exist_ok=True)
    country_eligible = [
        item for item in eligible
        if item.get("status") in {"FIXED_CANDIDATE", "FIXED_VERIFIED"}
    ]
    for item in country_eligible:
        code = item.get("country_code")
        if code and code != "XX" and len(str(code)) == 2:
            target = country_dir / f"{str(code).upper()}.txt"
            existing = target.read_bytes() if target.exists() else b""
            old_uris = decode_existing(existing, encoding)
            target.write_bytes(encode_uris(old_uris + [item["uri"]], encoding))
    for protocol in ("vless", "vmess", "trojan", "ss"):
        items = [item for item in eligible if item.get("protocol") == protocol]
        (protocol_dir / f"{protocol}.txt").write_bytes(
            encode_uris(ordered(sorted(items, key=lambda item: item["config_id"])), encoding)
        )
    return {name: len(uris) for name, uris in outputs.items()}


def decode_existing(payload: bytes, encoding: str) -> list[str]:
    if not payload:
        return []
    if encoding == "base64":
        import base64

        raw = base64.b64decode(payload, validate=True).decode("utf-8")
    else:
        raw = payload.decode("utf-8")
    return [line.strip() for line in raw.splitlines() if line.strip()]
