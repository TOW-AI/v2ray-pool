# 03 - Collector

## Source registry

Each source has a unique ID, URL, format, enabled flag, priority, timeout, byte limit, redirect limit, trust level, and public redistribution flag. A source must have explicit permission for public redistribution.

## Fetch policy

The Collector accepts HTTP and HTTPS on ports 80 and 443. It rejects URL credentials, query strings, fragments, control characters, and unsafe ports. It resolves each host. It rejects non-global IP addresses. It pins the resolved IP for the HTTP request. It checks each redirect as a new request.

The Collector limits response size, time, and redirect count. It does not log source headers or source credentials.

## Parser

The Parser supports VLESS, VMess, Trojan, and Shadowsocks URI formats. It supports plain text, Base64 subscription text, and JSON input. It reports rejected rows. It does not treat a parsed URI as a validated endpoint.

## Normalization and IDs

Normalization must be deterministic. It must preserve connection semantics. The canonicalizer has a version. The `config_id` is the SHA-256 hash of the canonical URI representation.

## Deduplication

One canonical URI creates one config record. The record keeps every source ID that reported it.

## Acceptance checks

- Reject an unsafe source destination.
- Reject a redirect to a private address.
- Reject an oversized response.
- Reject invalid Base64 input.
- Keep one ID for duplicate URIs.
- Keep source provenance after deduplication.
