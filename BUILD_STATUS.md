# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-02-25 ~20:00 UTC

## Current Task

**Status:** Phase 12 complete, retros done, CLAUDE.md updates applied. Between phases.
**Branch:** `main`

### In Progress
- Nothing active

### Recently Completed
- **Phase 12: Video Capture** — PR #29, merged to main (ADR-0021)
- **Phase 12 retro** — RETRO-20260225b.md, discussion sealed, PR #30 merged
- **Phase 11 retro** — RETRO-20260225.md, discussion sealed, PR #30 merged
- **CLAUDE.md updates** — Principle 6 deferral clause + capture pipeline yield limitation (from Phase 11 retro, applied in PR #30)
- **Phase 11: Google Calendar + Reminders** — PR #28, merged (ADR-0020)
- **Phase 10: Location Awareness** — PR #27, merged (ADR-0019)
- **Phase 9: Photo Integration** — PR #26, merged (ADR-0018)

## Tech Debt

- **Coverage** — 77.2% (below 80% target). Phases 11+12 add platform-dependent code that requires device mocks.
- **Education gates deferred** — Phase 11 (OAuth, dual state machine, sealed patterns) + Phase 12 (video pipeline, metadata stripping, STT pause/resume). Two consecutive deferrals = Principle 6 violation. Must complete before Phase 13.
- **Phase 12 advisory findings** — 10 non-blocking items from REV-20260225-170000.md.
- **Phase 11 advisory findings** — 12 non-blocking items from REV-20260225-110000.md.
- **Path documentation mismatch** — ADR-0018 and ADR-0021 document localPath as relative, but actual stored values are absolute. DAO doc comments also say relative. Needs Known Issue notes on both ADRs.
- **review_gates.md updates needed** — advisory lifecycle tracking section + visible-data-correctness blocking rule (from RETRO-20260225b).
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

All phases (9-12) merged to main. Both retros complete. CLAUDE.md updated. Next actions from retros:
1. Complete education gates for Phase 11 + Phase 12 (hard prerequisite per Principle 6)
2. Coverage recovery sprint (target 80%+)
3. Fix path documentation (ADR-0018, ADR-0021 Known Issue notes, DAO doc comments)
4. Update review_gates.md (advisory lifecycle, visible-data-correctness rule)
5. Run `/batch-evaluate` for PENDING adoption patterns before 2026-03-05

Uncommitted working tree changes exist from earlier device testing (Gradle files, lib/ UI tweaks, test fixes). These are not part of any completed phase — review before committing.

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
