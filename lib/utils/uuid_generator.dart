// ===========================================================================
// file: lib/utils/uuid_generator.dart
// purpose: Thin wrapper around the uuid package for generating unique IDs.
//
// Why client-generated UUIDs?
//   Offline-first architecture (ADR-0004) requires creating records without
//   a server round-trip. UUIDs v4 are random enough that collisions are
//   astronomically unlikely, even when syncing across devices in Phase 4.
// ===========================================================================

import 'package:uuid/uuid.dart';

/// Single reusable Uuid instance — it's stateless and thread-safe.
const _uuid = Uuid();

/// Generate a new v4 UUID string.
///
/// Returns a lowercase, hyphenated UUID like:
///   'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
///
/// Usage:
///   final sessionId = generateUuid();
///   final messageId = generateUuid();
String generateUuid() => _uuid.v4();
