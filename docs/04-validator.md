# 04 - Validator

## Purpose

The Validator decides whether a parsed URI is safe to test. A valid result does not prove a working tunnel or a fixed IP.

## Syntax checks

Check the scheme, host, port, required credentials, and protocol fields. Reject malformed or unsupported values. Keep a specific error code.

## Destination checks

Reject loopback, private, link-local, multicast, reserved, and metadata addresses. Resolve every A and AAAA record. Reject a hostname if any resolved address violates policy. Use the validated address for the TCP preflight. Re-check DNS when a connection is made.

## TCP preflight

Use a short timeout. Record DNS failure, refused connection, timeout, and network failure as separate results. TCP reachability is not a protocol test.

## Logging

Do not log a complete connection URI. Do not log UUIDs, passwords, private keys, or tokens.

## Acceptance checks

- Invalid syntax does not crash the process.
- IPv4 and IPv6 results remain separate.
- Private DNS answers are blocked.
- Redirect and DNS changes cannot bypass policy.
- TCP failure is not reported as a syntax failure.
