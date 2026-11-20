# 10 - State and History

## State files

- `state/configs.json`: current configuration registry.
- `state/ip-history.json`: IP observations and classification events.
- `state/metrics.json`: latest metric records.

## History files

Store daily, ISO-weekly, and monthly Run records. Store timestamps in UTC. Keep Run IDs and Test IDs. Do not infer missing observations.

## Append-only evidence

Do not remove an IP observation when the classification changes. Add a new event. Keep the original time, observer, and result.

## Retention

The engine archives old daily, weekly, and monthly files. It writes a compressed archive. It verifies the decompressed SHA-256 hash. It records the file path, size, hash, and archive time in an append-only manifest. It removes the hot copy only after verification.

## Recovery

Run `python -m engine.cli audit-state`. The command checks the State structure and each archive listed in the manifest. Restore from a verified backup or archive. Report records that cannot be recovered.
