---
adr_id: ADR-0002
title: "Flutter/Dart Cross-Platform Tech Stack"
status: accepted
date: 2026-02-18
decision_makers: [developer]
discussion_id: null  # Pre-framework decision — documented from product brief
supersedes: null
risk_level: high
confidence: 0.90
tags: [tech-stack, flutter, dart, cross-platform]
---

## Context

The Agentic Journal project requires a cross-platform mobile app (Android primary, iOS secondary) that supports offline-first data storage, AI-powered conversations, and registration as the Android default digital assistant. The developer has deep Python/SQL Server expertise and is learning mobile development.

Key requirements driving the choice:
- Cross-platform from day one (Android + iOS from a single codebase)
- Offline-first with local SQLite storage
- AI tooling ecosystem compatibility
- Approachable for a Python developer
- Platform channel support for Android assistant gesture registration

## Decision

Use **Flutter 3.x + Dart** as the application framework, with the following core libraries:

- **Riverpod** for state management (modern, testable, less boilerplate than Bloc)
- **drift** for local SQLite database (type-safe SQL that leverages existing SQL expertise)
- **dio** for HTTP client (interceptors for auth, retry logic, logging)
- **workmanager** for background sync scheduling
- **flutter_secure_storage** for secure token/key storage
- **connectivity_plus** for online/offline state detection

## Alternatives Considered

### Alternative 1: React Native + TypeScript
- **Pros**: Large ecosystem, JavaScript familiarity, Expo for rapid prototyping
- **Cons**: Bridge architecture adds latency, SQLite support less mature (no drift equivalent), platform channel support more complex for assistant registration
- **Reason rejected**: Dart's type-safe SQL via drift is a better fit for a SQL-experienced developer; Flutter's compiled-to-native approach provides better performance for offline-first patterns

### Alternative 2: Native Kotlin (Android) + Swift (iOS)
- **Pros**: Best platform integration, no cross-platform overhead, native assistant registration
- **Cons**: Two codebases to maintain, doubles development effort, developer unfamiliar with both Kotlin and Swift
- **Reason rejected**: Cross-platform requirement makes maintaining two native codebases impractical for a solo developer

### Alternative 3: Kotlin Multiplatform (KMP)
- **Pros**: Shared business logic, native UI, growing ecosystem
- **Cons**: UI still platform-specific (Compose + SwiftUI), ecosystem less mature than Flutter, smaller community for troubleshooting
- **Reason rejected**: Flutter's single-codebase UI approach is simpler; KMP's maturity gap adds risk for a learning developer

## Consequences

### Positive
- Single codebase for Android and iOS
- Dart's syntax similarity to Python reduces learning curve
- drift provides type-safe SQL queries familiar to a SQL developer
- Riverpod's explicit dependency injection aligns with Python's "explicit > implicit" philosophy
- Strong platform channel support for Android assistant integration
- Hot reload accelerates development iteration

### Negative
- Flutter apps have larger binary size than native (~15-25 MB overhead)
- Platform channel required for Android assistant gesture (small native Kotlin bridge)
- Dart ecosystem is smaller than JavaScript/TypeScript for third-party packages
- Developer must learn Dart alongside Flutter framework concepts

### Neutral
- Flutter's widget-based UI model is different from web frameworks but well-documented
- Code generation (drift, freezed) adds a build step (`dart run build_runner build`)

## Linked Discussion
Pre-framework decision — documented from product brief (`docs/product-brief.md`, Tech Stack section).
