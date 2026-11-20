# 08 - Subscriptions

## Purpose

The Distribution layer converts eligible records into client subscription files. It does not test a tunnel or classify an IP.

## Publication policy

A source must allow public redistribution. A record must have `public_redistribution: true`. The engine blocks invalid, quarantined, expired, and IP-unverified records from subscription output. The Fixed Verified file accepts only Fixed Verified records.

## Encoding

The default encoding is Base64. The engine first creates one UTF-8 URI per line. It then encodes the complete byte sequence. It writes one Base64 line. Use `plain` only when the target client requires it.

## Country files

Use the verified egress IP for GeoIP lookup. Do not use the server destination or the GitHub Runner location. Do not create country data when no verified fixed egress IP exists.

## Quality gate

Decode each subscription. Parse every URI. Check for duplicates. Compare the Fixed Verified file with State. Reject secret patterns and sensitive file types. Do not publish a partial snapshot.
