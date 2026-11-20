# Security Policy

## Scope

This project handles untrusted source URLs and untrusted connection URIs. It starts local Xray processes. It writes public data to a Git branch.

## Report a vulnerability

Do not publish a vulnerability report with a live configuration URI, access token, private key, or personal data. Use the private security contact for the repository owner. The repository must define that contact before public release.

## Response rules

1. Disable the affected source or workflow.
2. Stop public publishing.
3. Revoke exposed credentials.
4. Preserve run IDs and commit IDs.
5. Reproduce the issue with a non-secret test case.
6. Add a regression test.
7. Publish a corrective commit. Do not rewrite public history to hide the event.

## Supported security controls

The engine checks source redirects, DNS results, destination addresses, response sizes, process time, Xray hashes, public output, and archive integrity. These controls reduce risk. They do not prove that the system has no vulnerabilities.
