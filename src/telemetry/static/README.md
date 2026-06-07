# Vendored frontend assets — Telemetry Layer B dashboard

These files are vendored (not fetched from a CDN at runtime) per
SPEC-20260607-183136 R11a / AC6, which eliminates the only outbound load-time
dependency and the SRI/CDN-compromise surface. The FastAPI app in
`scripts/telemetry/dashboard_server.py` serves this directory through a
`StaticFiles` mount.

## Pins

| Asset           | Version  | Source                                                          | Bytes  | Integrity (SHA384, base64)                                              |
| --------------- | -------- | --------------------------------------------------------------- | ------ | ----------------------------------------------------------------------- |
| `htmx.min.js`   | 1.9.12   | https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js              | 48101  | `sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2` |

Chart.js is intentionally **not** vendored in Phase 1 — Phase 1 has no charts.
It will be vendored when Phase 2 (time-series) lands; the same pin-and-integrity
discipline applies.

## Updating an asset

1. Download the new minified release from a verifiable source (the upstream
   release page is preferred; `unpkg` mirrors npm but is acceptable).
2. Verify the file's SHA384 matches the upstream-published integrity (or your
   own out-of-band download from the same release tag).
3. Replace the file, update the table above with the new version + bytes +
   integrity, and update any pinned tests that assert on the version string.
4. Run the quality gate; tests in `tests/test_dashboard_server.py` will catch a
   missing file at the `/static/` mount.

The repository is the integrity anchor: once a file is in the table above and
committed, any change to it is a code-review event, not a silent supply-chain
swap.
