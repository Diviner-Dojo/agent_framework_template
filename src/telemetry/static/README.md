# Vendored frontend assets — Telemetry Layer B dashboard

These files are vendored (not fetched from a CDN at runtime) per
SPEC-20260607-183136 R11a / AC6, which eliminates the only outbound load-time
dependency and the SRI/CDN-compromise surface. The FastAPI app in
`scripts/telemetry/dashboard_server.py` serves this directory through a
`StaticFiles` mount.

## Pins

| Asset                  | Trust model       | Version  | License (companion file)                                      | Source                                                              | Bytes  | Integrity (SHA384, base64)                                              |
| ---------------------- | ----------------- | -------- | ------------------------------------------------------------- | ------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------- |
| `htmx.min.js`          | third-party       | 1.9.12   | BSD-2-Clause (header comment in file)                         | https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js                  | 48101  | `sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2` |
| `chart.umd.min.js`     | third-party       | 4.4.7    | MIT (see [`LICENSE-chart.js.txt`](./LICENSE-chart.js.txt))    | https://unpkg.com/chart.js@4.4.7/dist/chart.umd.js                  | 205615 | `sha384-zYPBGXwO4633CABX/5Spf6emCKUJCfoOkhOMYyxMsatqQZPnDblmmOewfjsIVWCM` |
| `dashboard-chart.js`   | first-party       | 1.0.0    | first-party (this repository)                                 | in-tree (this repository)                                           | 28329  | `sha384-jfKiKyHEewZ/0Ys2Kgccpc6W1NcNyFDiC/gbpTaOVEvzCzx1w7OBINOioUJYMK63` |

### What the SHA-384 pin actually defends against

The pin is **machine-enforced** at CI time by
`tests/test_dashboard_server.py::test_vendored_*_sha384_matches_readme_pin`
(one regression test per asset). Any byte change to the vendored file fails the
build immediately — that is the primary supply-chain control here.

The primary integrity anchor going forward is **git history**: once the bytes
are committed, any future change is a code-review event by definition, and the
pin makes silently rewriting the file fail before merge.

> **Not browser SRI.** The `sha384-...` values in the table above are not used
> as `<script integrity="...">` attributes — the assets are served same-origin
> from this repository's static mount under a strict `script-src 'self'` CSP,
> so browser SRI would be redundant. The digests are CI-side integrity anchors
> only.

### The two-mirror cross-check — what it does and does NOT prove

At vendoring time the Chart.js bytes were downloaded from both
`https://unpkg.com/chart.js@4.4.7/dist/chart.umd.js` and
`https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.js` and the two
files were byte-identical with the same SHA-384. This is **CDN-side consistency
evidence**, not independent upstream verification — both CDNs pull from the same
npm registry, so a registry-level compromise (malicious publish of
`chart.js@4.4.7`, or a registry substitution) would produce identical tampered
bytes on both mirrors. The cross-check catches CDN-edge tampering only.

The **independent** provenance pointer is the upstream GitHub release tag:
[`https://github.com/chartjs/Chart.js/releases/tag/v4.4.7`](https://github.com/chartjs/Chart.js/releases/tag/v4.4.7)
— hosted separately from npm, with a different trust root. A re-vendoring
audit should cross-reference that tag's commit + release notes.

### First-party `dashboard-chart.js` integrity

`dashboard-chart.js` is a first-party file authored in this repository —
NOT a vendored third-party library. It is pinned in the same SHA-384 table
so byte-stability is machine-enforced: any future edit (intentional or
otherwise) must update the pin in lockstep, which keeps the file's
provenance auditable from the in-tree artifacts alone. The integrity
discipline here is the same as the vendored libraries above; the
"supply chain" is just the local commit history. A second-degree benefit:
the regression test that asserts the byte digest cannot drift forces
every modification through code review (failing CI on any silent byte
change).

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
