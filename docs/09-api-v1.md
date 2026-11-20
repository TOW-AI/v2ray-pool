# 09 - Static API v1

## Architecture

Version 1 is a static JSON API. GitHub Raw or GitHub Pages can serve the files. The API does not provide live queries.

## Endpoints

- `stats.json`
- `configs.json`
- `fixed.json`
- `rotating.json`
- `countries.json`
- `rankings.json`

## Common fields

Each endpoint includes `schema_version`, `generated_at`, `run_id`, `source_commit`, `data_commit`, and `data_age_seconds`.

## Public metadata

`configs.json` contains public records only. It includes the protocol, classification, IP family status, verified egress IP when allowed, country, test time, metrics, scores, score coverage, and reason codes. Raw URI is disabled by default.

## Consistency

Build every endpoint from one State snapshot. The quality gate checks JSON syntax, base fields, duplicate IDs, and Fixed status. A new incompatible contract requires a new API version.
