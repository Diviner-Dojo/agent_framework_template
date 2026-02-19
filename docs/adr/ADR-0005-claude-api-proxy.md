---
adr_id: ADR-0005
title: "Claude API via Supabase Edge Function Proxy"
status: accepted
date: 2026-02-18
decision_makers: [developer]
discussion_id: null  # Pre-framework decision — documented from product brief
supersedes: null
risk_level: high
confidence: 0.85
tags: [security, api, claude, proxy, edge-function]
---

## Context

The Agentic Journal app uses the Claude API for LLM-enhanced conversations (Phase 3+), including follow-up question generation, session summarization, mood/topic tagging, and memory recall queries. The Claude API requires an API key for authentication.

Mobile app binaries can be decompiled, and any API key embedded in the binary is extractable. This creates risks: unauthorized API usage, cost overruns, and key revocation affecting all users.

## Decision

**Never call the Claude API directly from the mobile app.** All LLM calls route through a **Supabase Edge Function** (Deno/TypeScript) that:

1. **Receives** conversation messages from the authenticated Flutter app
2. **Injects** the system prompt (stored server-side, updatable without app release)
3. **Calls** the Claude API with the API key stored as a Supabase secret
4. **Returns** the assistant response + structured metadata (summary, mood tags, people, topics)
5. **Enforces** rate limiting and cost control per authenticated user

The Claude API key is stored as a Supabase environment secret, never in client code or app binary.

## Alternatives Considered

### Alternative 1: Embed API Key in App Binary
- **Pros**: Simplest implementation, no server-side code needed, lower latency (one fewer hop)
- **Cons**: API key is extractable from APK/IPA; no rate limiting; no cost control; key revocation affects all users; system prompt visible in decompiled code
- **Reason rejected**: Unacceptable security risk for a production app handling personal journal data

### Alternative 2: Dedicated FastAPI Backend
- **Pros**: Full Python stack (familiar to developer), more control over logging, caching, prompt versioning, complex preprocessing
- **Cons**: Requires hosting infrastructure (VPS/container), operational burden (uptime, scaling, deployment), costs money from day one
- **Reason rejected**: Overkill for MVP; Edge Function provides the same proxying with zero infrastructure. Can migrate to FastAPI later if complex server-side logic is needed.

### Alternative 3: API Key via Secure Remote Config
- **Pros**: Key not in binary, can be rotated remotely
- **Cons**: Key still reaches the device (interceptable via MITM on rooted/jailbroken devices); no server-side rate limiting; no prompt management; merely obscures rather than solves the problem
- **Reason rejected**: Security through obscurity; the key is still client-side at runtime

## Consequences

### Positive
- API key never present in app binary or on device
- System prompts are server-side — update conversation behavior without app releases
- Rate limiting and cost caps can be enforced per user
- Future flexibility: swap Claude for another model, add caching, preprocessing, or A/B testing without client changes
- Edge Function is serverless — no infrastructure to manage, scales automatically

### Negative
- Adds network latency (app → Edge Function → Claude API → Edge Function → app)
- Edge Function is Deno/TypeScript (unfamiliar to the developer), though the proxy logic is simple
- LLM features require network connectivity (mitigated: Layer A rule-based agent handles offline gracefully)
- Supabase Edge Function free tier has invocation limits

### Neutral
- The proxy pattern is standard for mobile apps calling paid APIs
- Edge Function authentication uses the same Supabase Auth JWT the app already has
- The proxy surface area is small (~50 lines of TypeScript)

## Linked Discussion
Pre-framework decision — documented from product brief (`docs/product-brief.md`, API Proxy Decision section).
