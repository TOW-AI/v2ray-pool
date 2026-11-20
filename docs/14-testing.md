# 14 - Test Strategy

## Test levels

- Unit tests: parser, canonical ID, validation, IP consensus, transitions, ranking, API, and subscriptions.
- Integration tests: source parsing, State persistence, history, and complete offline pipeline.
- Xray integration tests: process lifecycle and tunnel requests. Run only with a verified binary and controlled network access.
- Security tests: SSRF, DNS rebinding, redirects, response limits, command injection, redaction, and dashboard output.

## IP classification acceptance

| Input evidence | Expected result |
|---|---|
| One Run with several agreeing observers | Not Fixed Verified |
| Three independent Runs over 24 hours | Fixed Candidate, if all evidence agrees |
| Six independent Runs over 72 hours | Fixed Verified, if all evidence agrees |
| Two Runs with two agreed IP values | Rotating |
| Observer disagreement in one Run | IP Unverified |
| Stale evidence | Not Fixed Verified |
| IPv4 fixed and IPv6 rotating | Separate family statuses |

## Output checks

Validate all JSON files. Decode all subscriptions. Parse every URI. Reject duplicate IDs. Confirm that Fixed Verified contains no other state. Scan public files for secret patterns and sensitive file types.

## Go / No-Go

Do not publish until the code checks, tests, State checks, output checks, and live Xray requirements pass. Unit tests alone do not approve production publishing.
