---
adr_id: ADR-0003
title: "Supabase as Cloud Backend"
status: accepted
date: 2026-02-18
decision_makers: [developer]
discussion_id: null  # Pre-framework decision — documented from product brief
supersedes: null
risk_level: medium
confidence: 0.85
tags: [backend, supabase, postgresql, auth, cloud]
---

## Context

The Agentic Journal app needs a cloud backend for:
- User authentication (email/password for MVP)
- Data sync (journal sessions and messages)
- Row Level Security (journal entries are deeply personal)
- Future RAG/semantic search via vector embeddings
- Claude API proxying (keeping API keys server-side)

The developer has strong SQL Server expertise and prefers SQL-native tools over NoSQL or proprietary APIs. The backend must have a generous free tier for MVP development and support for serverless functions (Edge Functions) to proxy Claude API calls.

## Decision

Use **Supabase** as the cloud backend, providing:

- **PostgreSQL** database with full SQL capabilities
- **Supabase Auth** for user authentication (email/password, magic link)
- **Row Level Security (RLS)** for per-user data isolation
- **pgvector** extension for future RAG/semantic search
- **Edge Functions** (Deno/TypeScript) for Claude API proxying
- **Realtime** subscriptions (available for future multi-device sync)

## Alternatives Considered

### Alternative 1: Firebase (Firestore + Cloud Functions)
- **Pros**: Mature ecosystem, excellent Flutter SDK, generous free tier, strong offline sync built-in
- **Cons**: NoSQL data model (Firestore) is a poor fit for relational journal data; no native SQL; vendor lock-in to Google; no pgvector equivalent for RAG
- **Reason rejected**: Developer's SQL expertise is wasted on Firestore's document model; no path to vector search without adding another service

### Alternative 2: Dedicated FastAPI Backend + PostgreSQL
- **Pros**: Full control, familiar Python stack for the developer, easy to add complex server-side logic
- **Cons**: Requires hosting infrastructure (VPS/container), more operational burden, must implement auth and RLS manually, no free tier equivalent
- **Reason rejected**: Too much infrastructure for MVP; Supabase provides the same PostgreSQL + Auth + RLS with zero ops. Can migrate to dedicated backend later if needed.

### Alternative 3: Appwrite
- **Pros**: Open-source, self-hostable, REST/GraphQL APIs, built-in auth
- **Cons**: Smaller community than Supabase, less mature PostgreSQL integration, no pgvector, Flutter SDK less polished
- **Reason rejected**: Supabase's direct PostgreSQL access and pgvector support better serve the RAG roadmap

## Consequences

### Positive
- SQL-native backend aligns with developer's expertise
- RLS provides data isolation without application-level enforcement
- pgvector is ready for semantic search when Phase 5 reaches RAG
- Edge Functions eliminate need for separate API proxy infrastructure
- Generous free tier covers MVP development and early users
- Direct PostgreSQL access means standard SQL tooling works

### Negative
- Vendor dependency on Supabase (mitigated: standard PostgreSQL underneath, portable)
- Edge Functions use Deno/TypeScript (unfamiliar to the developer, but small surface area)
- Free tier has limits on database size and Edge Function invocations
- Supabase client SDK adds a dependency to the Flutter app

### Neutral
- Supabase migrations use standard SQL files
- Auth tokens are JWTs (standard, inspectable, compatible with flutter_secure_storage)

## Linked Discussion
Pre-framework decision — documented from product brief (`docs/product-brief.md`, Tech Stack and Security sections).
