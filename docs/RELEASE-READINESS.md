# Release Readiness

## Package

- [x] Source code is present.
- [x] Configuration and JSON schemas are present.
- [x] Unit and offline integration tests are present.
- [x] Dashboard files are present.
- [x] GitHub workflows are present.
- [x] Project manuals are present.
- [x] The original Persian specification is present.
- [x] The implementation package passes local acceptance checks.
- [ ] The package is not ready for live production use.

## Production blockers

1. Add only approved public sources.
2. Install Xray v26.10.31 and verify the official SHA-256 value.
3. Enable Xray only after the hash check passes.
4. Run live connectivity and IPv4/IPv6 observer tests.
5. Supply a GeoIP database if country output is required.
6. Create and protect the `data` branch.
7. Run the GitHub validation workflow.
8. Run one controlled production update.
9. Review the public data diff before enabling the schedule.
10. Confirm GitHub Pages and the dashboard API path.

## Release decision

The ZIP is a complete implementation package for local review and CI validation. The local test suite passes. Live infrastructure has not passed acceptance. The release remains blocked for production use until all production blockers are closed.
