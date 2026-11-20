# Security Review Report

## Review scope

This review covers source fetching, URI parsing, endpoint validation, Xray execution, observer requests, State and History handling, public distribution, dashboard rendering, and Git publishing.

## Findings fixed during implementation

1. The validator lacked a required DNS import. The import is present.
2. Invalid port values did not return a specific error. Port errors are now explicit.
3. A failed observer observation could retain an old Fixed Verified status. A new invalid observation now suspends the fixed claim.
4. A record that changed IP could not build a new stable evidence window correctly. The classifier now starts a new evidence streak after the last change.
5. Ranking could include records without public redistribution approval. Ranking now filters those records.
6. Protocol subscriptions could include a non-publishable record. Subscription generation now filters status and approval.
7. Country metadata could remain attached to a rotating or unverified address. Country data now requires a verified fixed egress address.
8. The observer layer did not issue distinct family-specific requests. It now queries IPv4 and IPv6 separately and validates the returned address family.
9. History retention had no verified archive path. It now compresses, hashes, verifies, and manifests old history before deleting the hot copy.
10. A publish job could start from an older data branch state. The publisher now checks the expected parent commit.
11. Malformed Shadowsocks input could stop a complete source parse. Parser errors are now isolated to the affected record.
12. Invalid decoded fields could contain control characters. Parser validation now rejects control characters before test configuration generation.
13. A History manifest could contain a path traversal value. Archive verification now rejects absolute paths, parent traversal, backslashes, and paths outside the archive root.
14. The static security audit initially rejected a safe subprocess command variable. The audit now checks that all subprocess calls set `shell=False` and use a command sequence.
15. Source response headers had no read limit. The Collector now rejects header files above 64 KiB before it parses a redirect.
16. A conflicting observation set within one Run could retain older Fixed evidence. The classifier now resets the stability window after that Run.
17. Python `preexec_fn` is unsafe in a multithreaded process pool. The Xray runner now applies Linux limits through `prlimit`.

## Controls in the package

- HTTP and HTTPS source policy. Ports 80 and 443 only.
- Public DNS result checks and pinned fetch address.
- Redirect checks for each hop.
- Response body and header size limits, plus timeout limits.
- No shell for external process commands.
- Xray version and SHA-256 checks.
- Xray process timeout and cleanup.
- Linux process limits are applied through `prlimit` without a Python pre-exec hook.
- Observer requests through the local SOCKS proxy.
- No observer redirect. Bounded response size.
- Public redistribution approval.
- Disabled raw URI publication by default.
- Safe dashboard DOM rendering.
- State and history consistency checks.
- Archive integrity checks.
- Expected-parent check and normal Git push.
- Static audit of Python dangerous calls, subprocess shell settings, and unsafe JavaScript sinks.

## Residual risk

This review does not prove that no vulnerability exists. Live Xray, production DNS, external observer health, GitHub token permissions, branch protection, and external penetration testing remain unverified.
