# 00 - System Overview

## Purpose

The engine collects public V2Ray connection URIs. It validates each record. It tests each eligible record with Xray. It records egress IP evidence. It classifies IP stability. It ranks measured performance. It creates public subscriptions and static API files.

## Product priority

The first priority is proof of egress IP stability. The second priority is connection quality. A single successful test does not prove a fixed IP.

## System boundaries

The system runs as a scheduled batch pipeline in GitHub Actions. It writes a complete snapshot to the `data` branch. The dashboard reads static JSON files. Version 1 does not provide a live backend.

## Success criteria

For each published record, the API must show its stable ID, protocol, status, last test time, IP family, evidence count, evidence period, and measured metrics. A ranking must show its measured components and coverage.

## Non-goals

- The system does not promise tests from every country.
- The system does not promise continuous uptime.
- The system does not prove ownership of an egress IP.
- The system does not keep public subscription credentials secret.
- The system does not create a live API server.

## Release rule

Do not call a function complete until code, tests, and output checks support the claim.
