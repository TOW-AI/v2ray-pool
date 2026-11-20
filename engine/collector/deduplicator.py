"""Deduplicate parsed configurations by stable config_id."""

from engine.models import ParsedConfig


def deduplicate(configs: list[ParsedConfig]) -> tuple[list[ParsedConfig], int]:
    records: dict[str, ParsedConfig] = {}
    duplicates = 0
    for config in configs:
        if config.config_id in records:
            duplicates += 1
        else:
            records[config.config_id] = config
    return list(records.values()), duplicates
