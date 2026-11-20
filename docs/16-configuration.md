# 16 - Configuration Reference

Settings are stored in `config/settings.yml`. The engine validates them against `schemas/settings.schema.json`.

| Section | Key settings |
|---|---|
| Collector | timeouts, response bytes, redirects, concurrency, refresh interval |
| Validator | allowed protocols, blocked IP classes, TCP timeout, denied ports |
| Tester | Xray path, Xray version, SHA-256, timeouts, concurrency, observers, IPv4 and IPv6 |
| Intelligence | Candidate and Verified thresholds, Rotating threshold, evidence age, required families |
| Ranking | policy version, metric age, coverage, Fixed / Rotating / Balanced weights |
| Subscription | Base64 or plain, main-file policy, top list size |
| API | schema version, raw URI policy |
| History | daily, weekly, and monthly retention periods |
| Scheduler | cron expression and concurrency group |

## Security requirements

Do not store tokens in YAML. Do not use an authenticated source URL. Store required secrets in the GitHub secret store or an approved runtime secret store.

## Policy review

The default thresholds and ranking weights are initial policy values. Review them before production. Record a policy version when you change them.
