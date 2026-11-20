# 07 - Ranking

## Rules

Use measured values only. Do not convert a missing metric to zero. Store a measurement time, method, and unit. Reject non-finite values.

## Ranking groups

- Fixed: prioritize verified IP stability, connection success, latency, uptime estimate, and freshness.
- Rotating: use connection success, latency, uptime estimate, and freshness.
- Fastest: sort by fresh measured latency, from low to high.
- Balanced: use the configured multi-metric weights.

## Score policy

Each ranking policy has a version. The configured weights must sum to 1. Each score must show its components and `score_coverage`. The engine excludes incomplete records below the minimum coverage value.

## Deterministic order

Use a stable tie-break value such as `config_id`. The same input snapshot must produce the same ranking.

## Acceptance checks

- Missing latency does not enter Fastest.
- Old measurements do not enter a current ranking.
- Fixed and Rotating scores remain separate.
- A score shows its coverage and policy version.
