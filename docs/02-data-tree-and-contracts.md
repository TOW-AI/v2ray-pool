# 02 - Data Tree and Contracts

## Public data tree

```text
data/
├── sub/
│   ├── main.txt
│   ├── fixed.txt
│   ├── fixed-verified.txt
│   ├── fixed-top50.txt
│   ├── rotating.txt
│   ├── rotating-top50.txt
│   ├── fastest.txt
│   ├── balanced.txt
│   ├── country/<CC>.txt
│   └── protocol/{vless,vmess,trojan,ss}.txt
├── api/v1/{stats,configs,fixed,rotating,countries,rankings}.json
├── history/{daily,weekly,monthly}/
├── history/archive/
├── state/{configs,ip-history,metrics}.json
└── README.md
```

## Data format

Use UTF-8. Use UTC ISO 8601 timestamps. Use JSON schema version `1.0.0`. Use `null` for unknown values. Do not use zero for an unknown measurement. Use `sha256:<hex>` for `config_id`.

## Subscription rules

Use one configured encoding for all subscription files. The default is Base64. Encode one URI per line. Do not add headers or comments. An empty subscription must be a zero-byte file.

- `main.txt`: approved records that pass publication policy.
- `fixed.txt`: Fixed Candidate and Fixed Verified records.
- `fixed-verified.txt`: Fixed Verified records only.
- `fixed-top50.txt`: up to 50 Fixed Verified records.
- `rotating.txt`: records with verified IP changes across Runs.
- `rotating-top50.txt`: up to 50 Rotating records.
- `fastest.txt`: records with fresh latency measurements.
- `balanced.txt`: records that pass score coverage policy.
- `country`: records grouped by verified egress country.
- `protocol`: records grouped by parsed protocol.

## API files

All API files include `schema_version`, `generated_at`, `run_id`, `source_commit`, `data_commit`, and `data_age_seconds`. All endpoints use the same snapshot.

`configs.json` contains public metadata. It omits raw URI by default. The public data branch must not contain private records or secrets.

## State and history

State is the current record set. History stores old observations and events. IP observations are append-only. History retention compresses old files. The engine verifies each archive against its SHA-256 manifest before it deletes the hot copy.
