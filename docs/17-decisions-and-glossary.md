# 17 - Decisions and Glossary

## Architecture decisions

| Topic | Decision |
|---|---|
| Runtime | GitHub Actions batch pipeline |
| Data branch | `data` |
| Code branch | `main` |
| Priority | Egress IP stability evidence |
| Classification | Fixed, Rotating, Unstable, and Unverified are separate |
| Distribution | Text subscriptions, static API, static dashboard |
| History | Append-only evidence with verified archive |
| Publish | Atomic snapshot and normal Git push |

## Open production decisions

Review the following settings before live operation: Fixed thresholds, evidence age, observer list and quorum, ranking weights, metric age, subscription encoding, Rotating inclusion in `main.txt`, retention periods, and raw URI exposure.

## Glossary

| Term | Definition |
|---|---|
| Config | A V2Ray connection URI. |
| `config_id` | Stable ID from the canonical URI. |
| Run | One independent pipeline execution. |
| Test | One test of one configuration. |
| Egress IP | Public IP that a remote destination sees through the tunnel. |
| Observer | A service that reports the request IP. |
| Consensus | Agreement between valid observers in one observation. |
| Fixed Candidate | A record with initial evidence for one IP. |
| Fixed Verified | A record that meets the current stable-IP evidence policy. |
| Rotating | A record with different agreed IPs across independent Runs. |
| IP Unverified | An observation without valid quorum or consensus. |
| State | The current system snapshot. |
| History | The record of previous observations and events. |
| Subscription | A text file with connection URIs. |
| Atomic publish | Replacement of a complete output snapshot. |

## Decision rule

Choose evidence quality over a larger configuration count. Do not reduce a threshold only to increase the number of Fixed records.
