---
name: severity-calibration
description: Shared severity-calibration rubric for specialist agents. Use when writing findings in /review, /plan, /build_module, or any other specialist output. Ensures honest severity at the source so the capture pipeline's explicit-marker parse (ADR-0022 R2.3) can be trusted.
---

# Severity Calibration Rubric

> Specialist agents: state an explicit `Severity: <tier>` marker for every finding so the
> capture pipeline can parse it correctly (see `_classify_severity` in
> `scripts/extract_findings.py`). Ambiguous cases default **down** — if you are unsure
> between two adjacent tiers, pick the lower one.

## Tier Definitions

### CRITICAL
**Scope**: Active exploitability or data loss in the current code path — an attacker can
trigger the impact without preconditions.

**One-sentence test**: Would a motivated attacker be able to cause data loss, privilege
escalation, or unauthorized access by calling this code as-is, today?

**Framework example**: A `/review` webhook endpoint that writes user-supplied content to
`events.jsonl` without sanitizing YAML/JSON metacharacters, allowing discussion-record
injection.

**Marker**: `Severity: CRITICAL`

---

### HIGH
**Scope**: Plausible exploitability, or a correctness bug with a user-visible consequence
that degrades trust or data integrity — requires non-trivial precondition or specific
configuration.

**One-sentence test**: Under a realistic but non-default scenario, does this bug cause
wrong output, data corruption, or a security weakness a defender would want to fix before
the next release?

**Framework example**: `_classify_severity` scanning the full event body instead of the
summary, causing any event mentioning "injection" in passing to be classified `critical`
— wrong data propagates silently through the knowledge loop.

**Marker**: `Severity: HIGH`

---

### MEDIUM
**Scope**: Code smell, maintainability concern, or theoretical risk that has no realistic
immediate exploit path but degrades the codebase over time.

**One-sentence test**: Would a reasonable senior engineer want this fixed in the next
sprint (but not in a hotfix)?

**Framework example**: `mine_patterns.py` lacking an `AND is_noise = 0` filter — noise
findings inflate the pattern-mining corpus and dilute promotion candidates, but no data
is lost.

**Marker**: `Severity: MEDIUM`

---

### LOW
**Scope**: Style, minor improvement, or a suggestion that has no functional impact.

**One-sentence test**: Would this finding appear on a style-guide linting report rather
than a correctness or security audit?

**Framework example**: A docstring that describes a parameter name that was renamed during
refactoring — stale but harmless.

**Marker**: `Severity: LOW`

---

### INFO
**Scope**: Observation with no action required — recorded for awareness, not remediation.

**One-sentence test**: Is this purely informational, with nothing to fix or improve?

**Framework example**: Noting that a script imports a private symbol cross-module by
design (documented in ADR-0022) — a fact, not a defect.

**Marker**: `Severity: INFO`

---

## Default-Down Rule

When a finding could reasonably be either HIGH or MEDIUM, mark it **MEDIUM**.
When it could be either CRITICAL or HIGH, mark it **HIGH**.
Asymmetric anchoring prevents severity inflation: the distribution should look like a
pyramid (few critical, moderate high, many medium/low), not an inverted one.

## Required Format

Every finding must carry a severity marker on its own line:

```
Severity: HIGH

The `_classify_severity` function matches patterns against the full event body …
```

or inline:

```
[HIGH] `mine_patterns.py` — both query branches lack `AND is_noise = 0` …
```

Both forms are recognized by the capture pipeline's `_EXPLICIT_SEVERITY_RE` pattern.

> **Note**: Accepted marker shapes (empirically pinned by
> `tests/test_extract_findings_classify_severity.py::test_explicit_marker_form_variants_parse`):
> `Severity: HIGH`, `severity=medium`, `[HIGH]`, `[HIGH: detail]`, `**HIGH**:`, `*LOW*:`,
> bare `**HIGH**`, and `(severity: medium)` — the tier word may be followed by `]`, stars,
> colon, whitespace, common punctuation (`.,;)`), or end-of-line. The safest canonical forms
> remain `Severity: HIGH` on its own line or `[HIGH]` inline; exotic decorations beyond the
> pinned set fall through SILENTLY to keyword heuristics (no error), so stick to these.
