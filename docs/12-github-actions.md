# 12 - GitHub Actions

## Branch model

- `main`: source code, settings, schemas, tests, and documents.
- `data`: public subscriptions, API, State, and History.
- `feature/*`: development work.

Create the `data` branch before the first publish.

## Workflows

- `validate.yml`: lint, type check, security scan, tests, and offline output checks.
- `update.yml`: scheduled or manual production pipeline.
- `maintenance.yml`: State and archive audit.
- `pages.yml`: deploy the dashboard and the latest static API files to GitHub Pages.

## Permissions

The build job uses `contents: read`. The publish job uses `contents: write`. Do not pass the write token to source collection or Xray tests.

## Publish sequence

The build job records the source data commit. The publish job checks that the data branch still has the same parent commit. If it changed, stop. The publisher commits a complete snapshot and performs a normal push. Do not force-push.

## Concurrency

Use one concurrency group for the data pipeline. Do not cancel a run that may contain the only copy of new evidence.

## Geographic limits

GitHub-hosted runners do not provide a guaranteed country exit point. Global source collection is not global network testing.
