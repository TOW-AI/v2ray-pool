# 13 - Security Review

## Assets

Protect GitHub tokens, source credentials, connection URIs, Xray binaries, State, History, Runner resources, and public API integrity.

## Threats and controls

| Threat | Required control |
|---|---|
| SSRF | Resolve and block non-global addresses. Pin the resolved address. |
| DNS rebinding | Re-check resolution before the connection. |
| Unsafe redirects | Disable automatic redirects. Revalidate each target. |
| Command injection | Use argument arrays. Set `shell=False`. |
| Malicious Xray binary | Pin the version and verify SHA-256. |
| Process exhaustion | Set time, memory, and concurrency limits. |
| Secret leakage | Redact logs. Scan public output. |
| History loss | Keep append-only evidence and verified archives. |
| Publish race | Check the expected data commit. Use a normal push. |
| XSS | Use safe DOM text APIs. |
| Unapproved redistribution | Require explicit source and record approval. |

## Incident response

1. Disable the affected source.
2. Stop publishing.
3. Revoke exposed tokens.
4. Record the Run ID and commit ID.
5. Identify affected public data.
6. Publish a corrective commit.
7. Add a regression test.

## Audit limit

A code review cannot prove that every future input is safe. Run external security tests before production use. Do not describe this review as a penetration test.
