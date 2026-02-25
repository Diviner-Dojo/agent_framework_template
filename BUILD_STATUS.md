# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-25 ~21:30 UTC

## Current Task

**Status:** Device-testing fixes committed and merged. Between phases.
**Branch:** `main`

### In Progress
- Nothing active

### Recently Completed
- **Device-testing fixes** — PR #33, merged. Real llamadart wiring, Google Services Gradle plugin, GoogleAuthException, llmAutoLoadProvider, lint fixes. REV-20260225-210000.md (0 blocking, 17 advisory).
- **review_gates.md updates** — PR #32, merged. Visible-data-correctness rule + advisory lifecycle section.
- **BUILD_STATUS.md update** — PR #31, merged.
- **Phase 11+12 retros + CLAUDE.md updates** — PR #30, merged.
- **Phase 12: Video Capture** — PR #29, merged (ADR-0021)
- **Phase 11: Google Calendar + Reminders** — PR #28, merged (ADR-0020)

## Tech Debt

- **Coverage** — 77.2% (below 80% target). Phases 11+12 add platform-dependent code that requires device mocks.
- **Education gates deferred** — Phase 11 (OAuth, dual state machine, sealed patterns) + Phase 12 (video pipeline, metadata stripping, STT pause/resume). Two consecutive deferrals = Principle 6 violation. Must complete before Phase 13.
- **Phase 12 advisory findings** — 10 non-blocking items from REV-20260225-170000.md.
- **Phase 11 advisory findings** — 12 non-blocking items from REV-20260225-110000.md.
- **Path documentation mismatch** — ADR-0018 and ADR-0021 document localPath as relative, but actual stored values are absolute. DAO doc comments also say relative. Needs Known Issue notes on both ADRs.
- **Device-testing advisory findings** — 17 non-blocking items from REV-20260225-210000.md (missing tests, ADR-0017 amendment, Riverpod anti-pattern, duplicated model loading).
- **PENDING adoptions** — 9 patterns from 2026-02-19, approaching 14-day stale threshold on 2026-03-05. Recommend `/batch-evaluate`.

## Open Discussions

- None

## Key Decisions (Recent)

- ADR-0021: Video Capture Architecture (separate Videos table, FFmpegKit metadata strip, 60s duration cap, journal-videos bucket, feature-flagged sync)
- ADR-0020: Google Calendar Integration
- ADR-0019: Location Privacy Architecture
- ADR-0018: Photo Storage Architecture

## Blockers

- None

## Resume Instructions

All phases (9-12) merged to main. Retros, CLAUDE.md updates, review_gates.md updates, and device-testing fixes all committed. Next actions:
1. Complete education gates for Phase 11 + Phase 12 (hard prerequisite per Principle 6)
2. Coverage recovery sprint (target 80%+)
3. Fix path documentation (ADR-0018, ADR-0021 Known Issue notes, DAO doc comments)
4. Run `/batch-evaluate` for PENDING adoption patterns before 2026-03-05

Remaining uncommitted files: integration_test/, spike-models/, test/helpers/, test/providers/, logcat dumps, docs/framework-enhancements-inventory.md, device-testing-fixes.diff. These are test helpers, spike artifacts, and debug output — not part of any committed phase.

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
