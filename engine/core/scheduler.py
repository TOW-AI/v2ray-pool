"""Select deterministic configuration work for one pipeline run."""


def select_configs(configs: list, maximum: int, limit: int | None = None) -> list:
    selected = sorted(configs, key=lambda item: item.config_id)
    cap = max(0, int(maximum))
    if limit is not None:
        cap = min(cap, max(0, int(limit)))
    return selected[:cap]
