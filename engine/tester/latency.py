"""Summarize measured observer round-trip samples."""


def summarize_latency(samples: list[float]) -> dict:
    valid = sorted(float(value) for value in samples if value >= 0)
    if not valid:
        return {"latency_ms": None, "latency_p50_ms": None, "latency_p95_ms": None, "latency_samples_ms": []}
    p50_index = min(len(valid) - 1, int(round((len(valid) - 1) * 0.50)))
    p95_index = min(len(valid) - 1, int(round((len(valid) - 1) * 0.95)))
    return {
        "latency_ms": round(sum(valid) / len(valid), 3),
        "latency_p50_ms": round(valid[p50_index], 3),
        "latency_p95_ms": round(valid[p95_index], 3),
        "latency_samples_ms": valid,
    }
