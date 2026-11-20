# 01 - Architecture

## Data flow

`Sources -> Collector -> Parser -> Normalizer -> Deduplicator -> Validator -> Xray Tester -> IP Intelligence -> Ranking -> Distribution -> Quality Gate -> Publisher`

## Components

| Component | Responsibility |
|---|---|
| Collector | Fetch approved public sources with strict limits. |
| Parser | Parse VLESS, VMess, Trojan, and Shadowsocks URIs. |
| Normalizer | Apply stable and versioned URI normalization. |
| Deduplicator | Keep one record for each canonical ID. |
| Validator | Check syntax, destination policy, DNS, and TCP reachability. |
| Tester | Run the pinned Xray binary and measure the tunnel. |
| IP Intelligence | Compare independent observations across Runs. |
| Ranking | Calculate separate Fixed, Rotating, Fastest, and Balanced lists. |
| Distribution | Build subscriptions and API JSON from one state snapshot. |
| Core | Manage settings, state, history, pipeline, and publish. |
| Dashboard | Display static API data. |

## Pipeline order

1. Load settings and schemas.
2. Load State and History from the data branch.
3. Fetch approved sources.
4. Parse, normalize, and deduplicate records.
5. Validate syntax and security policy.
6. Run TCP preflight.
7. Run Xray tests when enabled.
8. Query IP observers through the tunnel.
9. Record measurements and evidence.
10. Classify each IP family.
11. Calculate rankings.
12. Build subscriptions, API, and history.
13. Validate every output.
14. Publish one complete snapshot.

## Reliability rules

Each stage must fail with a clear error code. A failure in one source must not remove valid data from another source. A failed publish must not change the data branch. The publisher must use a normal Git push.
