# Implementation Checklist and Audit Report

**Project:** V2Ray Pool Intelligence Engine 2.0  
**Specification:** `docs/SYSTEM-DOCUMENTATION.fa.md`  
**Implementation version:** 2.0.0  
**Audit date:** 2026-11-20  
**Decision:** Local implementation approved. Production deployment remains blocked.

## 1. Build and architecture checklist

- [x] Implement Collector, Parser, Normalizer, and Deduplicator.
- [x] Implement Syntax, Security, DNS, and TCP validation.
- [x] Implement the Xray process runner and binary integrity checks.
- [x] Implement independent IPv4 and IPv6 observer collection.
- [x] Implement IP evidence, Fixed, Rotating, and Unverified classification.
- [x] Implement metric-based Fixed, Rotating, Fastest, and Balanced ranking.
- [x] Implement subscription generation and static API v1.
- [x] Implement State, Run history, period rollups, and verified archives.
- [x] Implement the static dashboard.
- [x] Implement GitHub Actions validation, update, maintenance, and Pages workflows.
- [x] Preserve the original Persian specification.
- [x] Add controlled-English operating manuals.

## 2. Local test evidence

| Check | Result | Evidence |
|---|---|---|
| Unit and offline integration tests | PASS | 67 tests passed |
| Branch-aware test coverage | PASS | 66.94%; configured minimum 60% |
| Python compilation | PASS | `compileall` for `engine` and `scripts` |
| Static security audit | PASS | 42 Python files and 2 JavaScript files; no findings |
| Settings validation | PASS | Settings schema and policy checks passed |
| Offline pipeline | PASS | API: 6 files; subscriptions: 12 files; quality gate passed |
| Output validation | PASS | All generated JSON and subscription files passed |
| State and archive audit | PASS | State valid; archive manifest valid |
| Dashboard JavaScript syntax | PASS | `node --check` |
| Xray installer shell syntax | PASS | `bash -n` |
| GitHub workflow YAML syntax | PASS | Four workflow files parsed |
| Ruff | NOT RUN | Executable is not installed in this environment |
| Bandit | NOT RUN | Executable is not installed in this environment |
| mypy | NOT RUN | Executable is not installed; CI step is advisory |

## 3. Security checklist

- [x] Reject source URLs with credentials, query strings, fragments, control characters, or non-standard ports.
- [x] Resolve source hosts and block non-global destination IPs.
- [x] Revalidate every redirect target.
- [x] Pin each source request to a validated DNS address.
- [x] Bound source body size, response header size, redirect count, and request time.
- [x] Validate V2Ray URI syntax and required credentials.
- [x] Block private and special destination addresses before TCP or Xray tests.
- [x] Require a version-pinned Xray binary and a matching SHA-256 hash.
- [x] Run external processes without a shell.
- [x] Apply process timeout, resource limits, and cleanup.
- [x] Send observer requests through the local Xray SOCKS proxy.
- [x] Enforce observer quorum and IP-family checks.
- [x] Require explicit public redistribution approval.
- [x] Exclude unapproved and non-publishable records from public output.
- [x] Keep raw URI publication disabled by default.
- [x] Validate API and State schemas before publication.
- [x] Reject secrets and sensitive file types in the public data tree.
- [x] Reject unsafe archive manifest paths and verify archive hashes.
- [x] Reject stale data-branch parents and use normal Git push only.
- [x] Use safe DOM text insertion in the dashboard.
- [ ] Complete external penetration testing.

## 4. Fixed IP acceptance policy

- [x] Use separate IPv4 and IPv6 evidence.
- [x] Require at least two successful independent observers in each valid observation.
- [x] Require observer consensus. Disagreement does not mean Rotating.
- [x] Require at least three independent Runs over 24 hours for Candidate status.
- [x] Require at least six independent Runs over 72 hours for Verified status.
- [x] Suspend Fixed status after a newer invalid or conflicting observation.
- [x] Require a fresh evidence window after a confirmed IP change.
- [x] Expire evidence after the configured maximum age.

## 5. Production blockers

- [ ] Add only sources with documented public redistribution permission.
- [ ] Install the pinned Xray version and configure the verified binary SHA-256.
- [ ] Run live Xray connectivity tests.
- [ ] Verify IPv4 and IPv6 observer quorum from the production Runner.
- [ ] Supply and validate a GeoIP database if country output is required.
- [ ] Create and protect the target GitHub `data` branch.
- [ ] Run the GitHub Actions validation workflow.
- [ ] Run one controlled production update and review the public diff.
- [ ] Verify GitHub Pages and the API path.
- [ ] Obtain external technical review and owner approval.

## 6. Approval and limitations

The local implementation and offline output checks pass. This report records an internal engineering review. It is not an external audit, a penetration-test certificate, or proof of live network performance.

The project does not contain sample V2Ray configurations. Its source registry is empty. Xray execution is disabled until the binary path and binary hash are configured. The offline snapshot is empty by design. It does not create synthetic latency, throughput, uptime, or IP evidence.

The manuals use short sentences, active voice, consistent terms, and direct instructions. This is an ASD-STE100-oriented writing approach. It is not a claim of formal ASD-STE100 certification.
