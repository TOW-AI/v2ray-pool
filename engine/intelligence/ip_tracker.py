"""Append immutable observer evidence to the IP history ledger."""

from __future__ import annotations

import hashlib
import json


def append_observations(ledger: list[dict], result: dict) -> int:
    added = 0
    for family, item in result.get("ip_observation", {}).items():
        observation = {
            "config_id": result["config_id"],
            "run_id": result["run_id"],
            "observed_at": result["finished_at"],
            "ip_family": family,
            "ip": item.get("ip"),
            "observers": item.get("observers", []),
            "consensus": bool(item.get("consensus")),
            "geo": None,
            "result_code": item.get("result_code"),
        }
        observation_id = hashlib.sha256(json.dumps(observation, sort_keys=True).encode()).hexdigest()[:32]
        observation["observation_id"] = observation_id
        if not any(item.get("observation_id") == observation_id for item in ledger):
            ledger.append(observation)
            added += 1
    return added
