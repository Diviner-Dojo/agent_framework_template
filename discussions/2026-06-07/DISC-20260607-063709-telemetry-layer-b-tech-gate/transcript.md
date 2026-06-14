---
discussion_id: DISC-20260607-063709-telemetry-layer-b-tech-gate
started: 2026-06-07T06:37:23.743229+00:00
ended: 2026-06-07T06:39:12.825210+00:00
agents: [facilitator, steward]
total_turns: 2
---

# Discussion: DISC-20260607-063709-telemetry-layer-b-tech-gate

## Turn 1 — facilitator (evidence)
*2026-06-07T06:37:23.743229+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Steward TECH-DECISION gate for Layer B of the Telemetry & Oversight component (Steward condition #5: 'Layer B technology is its OWN gated decision; approving it must not regress the 16/25-DEFER weight bar'). Developer chose the form factor: a STATIC HTML INFOGRAPHIC generated locally at read-time from metrics/evaluation.db (no server, no live web app). This is the north-star dashboard for understanding the developer's AI use.
- **Files/scope**: NEW (future) scripts/telemetry/dashboard.py (read evaluation.db -> render a self-contained HTML file) + an HTML template. Pattern precedent: the existing /status command 'opens a browser-based infographic'. Surfaces the A1/A2/A3 data foundation (now COMPLETE + committed a639903): per-tier cost + coverage; failure/waste signals; value-vs-subscription leverage + estimate cross-check (coverage framing).
- **Developer-stated motivation**: The whole point of the component is a powerful Layer B dashboard for understanding AI use; A1/A2/A3 were the data foundation, now done. Developer is on a Claude Code subscription + individual account (local-only, no billing API).
- **Explicit constraints**: The 5 carried telemetry Steward conditions still hold — (1) compute-don't-store inviolable (the dashboard DERIVES every dollar/ratio at read from evaluation.db + config; persists NOTHING new); (2) any Layer C/meta-review hand-off = schema-bound AGGREGATES only, never transcript free-text, topic slug never printed; (3) NO telemetry into any live agent prompt (the dashboard is read/render-only, never feeds a Task prompt); (4) ADR-0013 accepted; (5) THIS gate = the Layer B tech decision. Static HTML is the least-complex option (Principle #8) vs the deferred heavier web-app option. Decision needed: APPROVE/REVISE/DEFER/DECLINE the static-HTML-generated-locally form factor + any binding conditions for its /plan.

---

## Turn 2 — steward (decision)
*2026-06-07T06:39:12.825210+00:00 | confidence: 0.88*
*tags: steward-gate, layer-b, approve, condition-5, principle-7*

## Verdict: APPROVE (0.88) — Layer B form factor = static HTML generated locally at read-time; greenlights a /plan (form factor + honesty rails only, NOT a feature set).
16/25-DEFER bar CLEARED not regressed: the deferral weight attached to the SERVER option (standing service, network surface, operational weight); a read-time render script with no server is categorically lighter on every axis -> Principle #8 ordering working. Reuses the accepted /status precedent (scripts/git_visualize.py). The disciplines are already implemented in Layer A (analyze_value.py: read-only/persists-nothing, typed honest-absence) -> correct build = 'render the existing honest outputs', not new measurement. Extraction lens: a read-time render the developer runs+owns, ephemeral local artifact, nothing leaves the box, concentrates nothing -> honest instrument the developer owns (PHILOSOPHY distribute-not-concentrate).

**BLOCKING conditions for the Layer B /plan (its /review must demonstrate each):**
1. Compute-don't-store inviolable — derive every figure at render from evaluation.db + config; persist NOTHING new (no cache/table/column/sidecar); REUSE analyze_cost/analyze_value/analyze_failures, no parallel computation. Any persistence-for-speed returns to this gate.
2. Aggregates-only; NO transcript free-text/prompt bodies; ntfy topic slug NEVER printed (incl. error/diagnostic paths in the generator).
3. NO telemetry into any live agent prompt (render-only; never a Task() input; KV-cache).
4. Honest-absence carries to the UI — n/a / not configured / not yet active / unavailable are FIRST-CLASS rendered states, visually distinct from a true zero; never a fabricated 0 or misleading bar. Highest-risk axis for a visual surface; /review must specifically probe it.
5. NO secrets baked into the artifact (no keys/credentials/topic/env-leaking paths; cost+fee figures may render as the developer's own data).

**DEVELOPER DECISIONS (Principle #7, resolve in /plan):**
6. GITIGNORE the generated HTML + pick its output location (it may contain personal cost figures + the subscription fee; mirror docs/handoff/ gitignored treatment). Governs whether personal financials could reach a remote.
7. Feature scope (metric set/layout/interactivity) is the /plan's call under developer approval — NOT this gate's. Resist 'live refresh'/'auto-open schedule'/any standing process (re-opens server-vs-script -> returns to this gate).

**ADVISORY:** mirror /status UX (generate+open, then a 5-6 line text summary); keep dashboard.py a thin render layer (math stays in src/telemetry); harden any template/file read like _otel_estimate (fixed path/within-root/size-cap); declare the transport-fidelity boundary + assert 'rendered figures match the Layer A CLI outputs'.

---
