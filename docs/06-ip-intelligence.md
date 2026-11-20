# 06 - IP Intelligence

## Evidence model

An observation contains a config ID, Run ID, time, IP family, IP address, observer results, consensus, and result code. One Run can contribute at most one observation per config and IP family.

## Status values

| Status | Meaning |
|---|---|
| `DISCOVERED` | The Collector found the URI. |
| `VALIDATED` | Syntax and security checks passed. |
| `TESTED` | At least one Xray test passed. |
| `FIXED_CANDIDATE` | Early independent evidence shows one IP. |
| `FIXED_VERIFIED` | The configured evidence threshold is met. |
| `ROTATING` | Separate Runs show different IPs with observer consensus. |
| `UNSTABLE` | The connection or evidence is not reliable. |
| `IP_UNVERIFIED` | Observer quorum or consensus is missing. |
| `QUARANTINED` | A security rule or unusual behavior blocks the record. |
| `EXPIRED` | The evidence or record is too old. |
| `INVALID` | The URI is invalid. |

## Default thresholds

The default policy needs three independent Runs over 24 hours for Candidate. It needs six independent Runs over 72 hours for Verified. Each Run needs at least two successful observers. All successful observers must agree.

The defaults are policy values. Review them before production use.

## Rotating rule

A record is Rotating only when at least two independent Runs show at least two different IPs. Each observation must have observer consensus. Observer disagreement in one Run is not proof of rotation.

## IP families

Classify IPv4 and IPv6 separately. A Fixed IPv4 result does not prove Fixed IPv6. The overall status must follow the required family policy.

## Evidence expiry

Expire old evidence. A new failed or conflicting observation must suspend an older Fixed Verified claim. A record that returns to a prior IP must complete a new evidence window before the engine verifies it again.

## Explanation

Every classification includes reason codes and timestamps. Keep the old evidence when a classification changes.
