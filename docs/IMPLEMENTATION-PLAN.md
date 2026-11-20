# Implementation Plan and Work Breakdown

## Work packages

| ID | Work package | Deliverable | Status |
|---|---|---|---|
| WP-01 | Requirements baseline | Source spec and architecture map | Complete |
| WP-02 | Data contracts | Settings and source schemas | Complete |
| WP-03 | Collector | Bounded fetch, parser, normalization, deduplication | Complete |
| WP-04 | Validator | Syntax, SSRF policy, DNS and TCP preflight | Complete |
| WP-05 | Xray tester | Pinned binary check, process lifecycle, proxy probe | Complete; live test blocked |
| WP-06 | Observer layer | Family-specific observer quorum | Complete; live observer test blocked |
| WP-07 | IP intelligence | Fixed / Rotating / Unverified classifier | Complete |
| WP-08 | Ranking | Measured Fixed, Rotating, Fastest, Balanced rankings | Complete |
| WP-09 | Distribution | Subscriptions and API v1 | Complete |
| WP-10 | State and history | State, Run history, verified archives | Complete |
| WP-11 | Dashboard | Static dashboard and safe DOM rendering | Complete |
| WP-12 | CI/CD | Validation, update, maintenance workflows | Complete; GitHub execution pending |
| WP-13 | Audit | Automated, security, and output checks | Local checks complete; external checks pending |
| WP-14 | Release package | ZIP and checksum | Complete after archive integrity verification |

## Task checklist

### Architecture and contracts
- [x] Map modules to the source architecture.
- [x] Create settings and source schemas.
- [x] Define State and History formats.
- [x] Define subscription and API outputs.
- [x] Preserve the original Persian specification in `SYSTEM-DOCUMENTATION.fa.md`.

### Engineering
- [x] Build the Collector and Parser.
- [x] Add DNS and redirect controls.
- [x] Add syntax, security, and TCP validation.
- [x] Add the Xray process runner.
- [x] Add independent IPv4 and IPv6 observers.
- [x] Add IP evidence classification.
- [x] Add metric-based ranking.
- [x] Add subscription and API builders.
- [x] Add append-only history and verified archives.
- [x] Add the static dashboard.

### Quality and security
- [x] Add unit and offline integration tests.
- [x] Add output validation.
- [x] Add state audit and archive integrity checks.
- [x] Add static source and dashboard security checks.
- [x] Add regression tests for parser errors, archive path traversal, and publish races.
- [x] Add safe public data policy.
- [x] Add non-force publishing and expected-parent checks.
- [ ] Run Ruff, mypy, and Bandit in a network-enabled CI runner.
- [ ] Run live Xray integration tests with a verified binary.
- [ ] Verify the live observer services from the production Runner.
- [ ] Verify the actual GitHub `data` branch and Pages deployment.

## Work acceptance

A completed code task needs tests and output validation. A live infrastructure task needs a real run and a recorded result. A checklist item must not pass because a mock or sample value exists.
