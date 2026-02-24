---
adr_id: ADR-0019
title: "Location Tracking — Opt-in Awareness with Privacy-First Design"
status: accepted
date: 2026-02-25
decision_makers: [facilitator, architecture-consultant, security-specialist]
discussion_id: DISC-20260224-183917-phase10-location-awareness-spec-review
supersedes: null
risk_level: medium
confidence: 0.88
tags: [location, privacy, gps, geocoding, phase-10]
---

## Context

Phase 10 adds location awareness to journal sessions. Users want to see where they were when they journaled ("San Francisco, CA"), but location data is inherently sensitive. The design must balance utility with privacy, especially given that the app syncs to Supabase cloud.

Forces at play:
- Full GPS precision (~10m) is unnecessary for "I journaled in San Francisco" and creates a movement diary risk if the database is compromised.
- The Android platform geocoder (reverse geocoding) routes requests through Google's servers, so raw coordinates are transmitted to Google even in "local-only" mode.
- Cloud sync (Supabase) is upload-only and user-controlled, but any data synced to the cloud expands the attack surface.
- The app already has precedents for privacy-sensitive data handling: EXIF stripping for photos (ADR-0018), API key proxying (ADR-0005).

## Decision

### 1. Opt-in Default (Location Off)

Location capture is **off by default**. Users must explicitly enable it in Settings. This prevents silent location tracking on upgrade and respects the sensitivity of GPS data.

### 2. Precision Reduction (2 Decimal Places, ~1.1km)

GPS coordinates are rounded to 2 decimal places **before storage** in the local SQLite database. This is a deliberate privacy tradeoff — not a display formatting choice. At 2 decimal places, coordinates identify a neighborhood (~1.1km radius), not an address. This prevents pinpointing a home or workplace from the stored data.

Rounding examples: `51.507456 → 51.51`, `-73.985 → -73.99`, `0.004 → 0.0`.

### 3. Raw-Local / Name-Only-Cloud Sync Boundary

- **Local SQLite**: Stores `latitude`, `longitude`, `locationAccuracy` (reduced precision), and `locationName`.
- **Supabase cloud**: Only `locationName` (human-readable string like "San Francisco, CA") is synced. Raw coordinates **never leave the device** via our sync pathway.
- **Enforcement**: A unit test asserts that the Supabase upsert payload does not contain `latitude`, `longitude`, or `location_accuracy` keys. This makes the exclusion load-bearing and regression-resistant.

### 4. Permission Strategy

- **Default**: `ACCESS_COARSE_LOCATION` — matches the ~1.1km precision we actually store.
- **Opt-in upgrade**: `ACCESS_FINE_LOCATION` available if user enables "High precision" in settings.
- **No background location**: `ACCESS_BACKGROUND_LOCATION` is not declared. Location is captured only at session start (foreground operation).

### 5. Geocoding Disclosure

The Android `Geocoder.getFromLocation()` API routes through Google's servers when Google Play Services is available. This means reduced-precision coordinates are sent to Google during reverse geocoding. The opt-in flow discloses this: "Location names are looked up using your device's location service, which may contact Google. Raw coordinates are not stored in your journal's cloud backup."

### 6. GPS Acquisition Strategy

- Try `getLastKnownPosition()` first (returns immediately if cached).
- Fall back to `getCurrentPosition()` with a **2-second timeout**.
- Accept any cached position regardless of staleness (even stale position is better than none for the fire-and-forget pattern).
- Fire-and-forget: location capture runs **after** session creation commits, never blocking the greeting.

### 7. No Retry for Failed Geocoding

If reverse geocoding fails (offline, no result, exception), `locationName` stays null permanently for that session. No retry mechanism is implemented — null is a valid final state. This simplifies the implementation and avoids a pending-state column or background job.

## Alternatives Considered

### Alternative 1: Full GPS Precision (No Rounding)
- **Pros**: Maximum accuracy for location context.
- **Cons**: Creates a detailed movement diary. If SQLite file is extracted (rooted device, backup), precise home/work addresses are exposed.
- **Reason rejected**: Unnecessary precision for journaling use case. "San Francisco" is sufficient; "123 Main St" is a liability.

### Alternative 2: On-Device-Only Geocoding
- **Pros**: No coordinate data sent to Google.
- **Cons**: No reliable on-device geocoding library exists for Flutter. Would require bundling a multi-GB place name database.
- **Reason rejected**: Disproportionate complexity for the marginal privacy gain, given that coordinates are already reduced to ~1.1km precision.

### Alternative 3: Opt-out Default (Location On)
- **Pros**: Higher adoption, users see location data immediately.
- **Cons**: Silent location tracking on upgrade violates privacy-first design principle.
- **Reason rejected**: Sensitive sensor access must be opt-in. Matches Android's own permission model philosophy.

## Consequences

### Positive
- Users get location context without exposing precise coordinates to cloud or disk forensics.
- Sync payload test prevents accidental coordinate leakage in future code changes.
- Opt-in default respects user autonomy and privacy expectations.
- "Clear Location Data" propagates to cloud via syncStatus=PENDING mechanism.

### Negative
- Geocoding sends reduced-precision coordinates to Google (acknowledged in disclosure).
- No retry means some sessions may permanently lack a place name if geocoded offline.
- 2-decimal-place rounding may feel imprecise to users who want exact location (mitigated by future "High precision" opt-in).

### Neutral
- Schema v4 migration adds 4 nullable columns — no existing data affected.
- Two new packages (`geolocator`, `geocoding`) added to dependency tree.

## Linked Discussion
See: discussions/2026-02-24/DISC-20260224-183917-phase10-location-awareness-spec-review/
