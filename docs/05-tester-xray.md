# 05 - Tester and Xray

## Binary control

The Tester requires a pinned Xray version and a verified SHA-256 value. It rejects a missing binary or a hash mismatch. Do not run an unverified binary.

## Test lifecycle

1. Verify the binary version and hash.
2. Build a temporary Xray configuration.
3. Bind a random local SOCKS port.
4. Start Xray without a shell.
5. Wait for the local proxy.
6. Send probes through the local proxy.
7. Query each enabled IP family through independent observers.
8. Measure latency and throughput when policy permits.
9. Stop the process group.
10. Remove temporary files.
11. Record the result with a Run ID and Test ID.

## Process isolation

Use time limits and resource limits. On Linux, use `prlimit` to set CPU, memory, and file-descriptor limits. Do not use a Python `preexec_fn` in the concurrent process pool. Use private file permissions for temporary configuration. Do not expose the URI in logs. Stop the process after success, failure, or timeout.

The pipeline runs tests in a bounded worker pool. Set `tester.max_parallel_configs` to the maximum number of Xray processes that can run at the same time. The default is two. Select a lower value when the Runner has limited CPU or memory.

## IP observers

An observer must use HTTPS. The request must pass through the Xray SOCKS proxy. Do not follow redirects. Limit response size. Parse the returned IP address. Confirm that the response family matches the requested family.

At least two observers must succeed. All successful observers in one observation must report the same IP. A mismatch means `IP_UNVERIFIED`.

## Latency and throughput

Measure latency through the tunnel. Record the method and time. Measure throughput only against a controlled endpoint. Enforce a byte limit and a time limit. Use `null` when a metric was not measured.

## Uptime

Calculate uptime from scheduled independent Runs. Do not describe the scheduled estimate as continuous monitoring.
