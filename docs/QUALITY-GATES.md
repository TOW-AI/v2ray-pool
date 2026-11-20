# Quality Gates

## Gate A - Source and design
- [x] Map the implementation to the submitted architecture.
- [x] Include the original Persian specification.
- [x] Define module boundaries and data contracts.
- [x] Define settings, source, State, and API schemas.
- [x] Write the project manuals in controlled English.

## Gate B - Code and tests
- [x] Run 67 unit and offline integration tests.
- [x] Achieve 66.94% measured branch-aware coverage.
- [x] Meet the configured 60% coverage threshold.
- [x] Compile all Python modules and scripts.
- [x] Pass the local static security audit.
- [x] Validate the JavaScript syntax.
- [x] Validate the shell script syntax.
- [x] Parse all GitHub Actions workflow YAML files.
- [ ] Run Ruff in the local environment. The executable is not installed.
- [ ] Run Bandit in the local environment. The executable is not installed.
- [ ] Complete mypy in the local environment. The executable is not installed. The CI step is advisory.

## Gate C - Data and output
- [x] Validate the settings schema.
- [x] Validate all six static API files.
- [x] Decode and validate all twelve subscription files.
- [x] Enforce `FIXED_VERIFIED` status in the fixed-verified subscription.
- [x] Keep unmeasured values as `null`.
- [x] Keep the public data tree free of sample configuration URIs.
- [x] Build the same API and subscription snapshot from one State image.

## Gate D - Security
- [x] Apply bounded source fetch policy.
- [x] Validate DNS results and every redirect target.
- [x] Block private, loopback, link-local, multicast, reserved, and non-global addresses.
- [x] Pin source requests to the validated DNS address.
- [x] Require a pinned Xray version and a verified binary SHA-256.
- [x] Run child processes without a shell.
- [x] Apply process timeout and cleanup rules.
- [x] Require public redistribution approval before publication.
- [x] Disable raw URI publication by default.
- [x] Scan the public output for secret patterns and sensitive file types.
- [x] Use safe text insertion in the dashboard.
- [x] Verify History archives before removal of hot copies.
- [x] Reject unsafe archive paths in the manifest.
- [x] Check the expected data-branch parent before publication.
- [ ] Complete external penetration testing.

## Gate E - Live acceptance
- [ ] Run Xray against a verified binary. The binary path and SHA-256 are not configured.
- [ ] Verify IPv4 and IPv6 observer quorum on the production Runner.
- [ ] Test source collection. The production source registry is empty.
- [ ] Enable GeoIP. A local database is not supplied.
- [ ] Run GitHub Actions in the target repository.
- [ ] Verify the `data` branch publish and GitHub Pages deployment.
- [ ] Obtain an external technical auditor or repository owner sign-off.

## Approval statement

The local implementation and offline output pass the defined acceptance gates. The package is approved for repository review and controlled setup. The production gate remains blocked. Do not enable scheduled publishing until every live gate passes.
