# Layer B dashboard — honest-absence reviewability artifacts (spec R3a / C4)

These are **fixture-generated** HTML samples of the telemetry dashboard in its key
states, produced for the `/review` to probe the highest-risk axis (C4): *can a
fabricated `0` look authoritative?* They carry **synthetic fixture data only** —
no real cost, fee, or transcript content, no ntfy slug.

Open each in a browser to inspect the visual states.

## Fidelity boundary (declared, per the smoke-test-fidelity lesson)

The spec asks for *screenshots*. Real PNG capture needs a headless browser
(Playwright/Chromium) that is **not available in this build environment**, so the
artifact is the **actual rendered HTML** instead of a rasterised image. This is
strictly higher-fidelity for a code review (a reviewer reads the real markup, CSS
classes, and copy — not a lossy image), and lower-fidelity for *pixel* layout
(font rendering / exact dashed-border appearance is not captured). The CSS that
carries the visual distinction (`.tile--absent` = dashed border + muted repeating
background + `.tile__icon`) is inline in every file and reviewable directly.

## The three states

| File | What it demonstrates |
|------|----------------------|
| `dashboard-state-A-all-absent.html` | **Empty DB / first run.** Every panel in its honest-absence state: cost + failures *analyzer-not-yet-run* tiles (with `analyze_cost.py` / `analyze_failures.py` action links), leverage *not-configured*, attribution *unavailable*, OTel *enable* link. 5 `data-state="absent"` containers; **no `$0` anywhere**. |
| `dashboard-state-B-truezero-uncosted-otel.html` | **True-zero vs absence, side by side.** Failures shows the normal **data** tile "No failure signals detected" (true zero — analyzer ran, found nothing), NOT the absence style. The cost panel shows an unknown tier rendered **uncosted** (not `$0`). A3 is configured (`5.00x` cumulative / `2.50x`/mo). OTel still renders its *enable* affordance (the one absence tile). |
| `dashboard-state-C-populated.html` | **Fully populated.** A failure row with a transcript-shaped signature (escaped), cost tiers, and a configured A3 panel. |

## What the `/review` C4 probe should verify

- Absence tiles are distinguishable from data tiles by **shape/icon + copy**, not
  color alone (WCAG 1.4.1) — `.tile--absent` (dashed) + `.tile__icon` + a plain-
  language `[what]. [why]. [action]` sentence.
- A **true zero** ("No failure signals detected") uses the **data** tile, visibly
  distinct from the *analyzer-not-yet-run* absence tile.
- No panel renders a fabricated `0` bar / `$0.00` where the honest value is absent
  or uncosted; an unknown tier reads **uncosted**.
- The OTel cross-check is a live `<a href="…monitoring-usage" target="_blank">`
  link, not a dead "unavailable" row.

Regenerate: the samples are built from the same pure `render_dashboard_html` the
app uses (see the generation block in the build discussion
`DISC-20260607-072951-build-telemetry-layer-b-dashboard`).
