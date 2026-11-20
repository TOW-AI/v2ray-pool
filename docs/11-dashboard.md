# 11 - Dashboard

## Architecture

The dashboard is a static web application. It reads API v1 JSON. It does not run Xray and it does not start tests.

## Views

The dashboard shows the overview, classification status, Fixed and Rotating rankings, Fastest and Balanced rankings, inventory, country data, protocol counts, and system health. It shows evidence counts and dates when the API provides them.

## Filters

Support filters for protocol, status, country, and config ID.

## Data display

Show UTC time. Show units. Show `null` as `Not measured`. Show a stale-data warning when the configured data age is exceeded. Do not label static data as live.

## Front-end security

Create DOM nodes with safe text content. Do not insert untrusted data as HTML. Do not print URIs or credentials in browser logs. Use fixed API paths and HTTPS.
