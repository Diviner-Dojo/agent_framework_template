// ===========================================================================
// file: supabase/functions/claude-proxy/index.ts
// purpose: Supabase Edge Function that proxies Claude API calls for the
//          Agentic Journal app. The Claude API key lives here as a secret,
//          NEVER in the mobile app (ADR-0005).
//
// This function:
//   1. Receives conversation messages from the authenticated Flutter app
//   2. Injects the journaling system prompt (server-side, not from client)
//   3. Calls the Claude API with the key stored as a Supabase secret
//   4. Returns the response + optional structured metadata
//
// Modes:
//   - "chat": Conversational follow-ups during a journaling session
//   - "metadata": End-of-session extraction of summary, mood, people, topics
//
// Security:
//   - API key is in Deno.env (Supabase secret), never in response
//   - Input validation: max 50KB payload, required fields checked
//   - Proxy secret enforced even in Phase 3 (prevents open-proxy abuse)
//   - Auth header checked if present (Phase 4: JWT validation required)
//   - Error responses never expose internal details or API key
//
// See: ADR-0005 (Claude API via Supabase Edge Function Proxy)
// ===========================================================================

// Supabase Edge Functions run on Deno. "serve" handles HTTP routing.
// @ts-ignore - Deno-specific import
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_PAYLOAD_BYTES = 50 * 1024; // 50KB payload cap (security-specialist)
const CLAUDE_API_URL = "https://api.anthropic.com/v1/messages";
const CLAUDE_MODEL = "claude-sonnet-4-20250514";
const MAX_TOKENS = 1024;

// ---------------------------------------------------------------------------
// System Prompts (server-side only — never sent from client)
// ---------------------------------------------------------------------------

// Journaling conversation prompt — used in "chat" mode.
// The {context} placeholders are filled from the request's context object.
const CHAT_SYSTEM_PROMPT = `You are a personal journal assistant. Your role is to help the user capture their day through natural, warm conversation.

Rules:
- Ask 2-3 focused follow-up questions to draw out details
- Focus on: what happened, how they felt, who they were with, what they learned
- Be warm but concise — keep questions focused, one at a time
- When the user seems done, provide a brief summary of what was captured
- Do NOT invent or assume details the user didn't mention
- Keep each response under 100 words`;

// Metadata extraction prompt — used in "metadata" mode after session ends.
const METADATA_SYSTEM_PROMPT = `You are a journal analysis assistant. Given a journal conversation, extract structured metadata.

Return ONLY a valid JSON object with these fields:
{
  "summary": "2-3 sentence summary of what was discussed",
  "mood_tags": ["list", "of", "moods"],
  "people": ["names", "mentioned"],
  "topic_tags": ["themes", "discussed"]
}

Rules:
- Only include items that were explicitly mentioned
- Do not invent or infer anything not stated
- mood_tags should be simple emotion words (happy, tired, stressed, etc.)
- people should be proper names only
- topic_tags should be broad categories (work, family, health, etc.)
- Return ONLY the JSON — no markdown fences, no explanation`;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface RequestBody {
  messages: Message[];
  context?: {
    time_of_day?: string;
    days_since_last?: number;
    session_count?: number;
  };
  mode: "chat" | "metadata";
}

interface ClaudeResponse {
  content: Array<{ type: string; text: string }>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Build the system prompt with context for chat mode.
 * Context values come from the client (computed from local data, not user input).
 */
function buildChatSystemPrompt(context?: RequestBody["context"]): string {
  if (!context) return CHAT_SYSTEM_PROMPT;

  const contextLines: string[] = [];
  if (context.time_of_day) {
    contextLines.push(`- Time of day: ${context.time_of_day}`);
  }
  if (context.days_since_last !== undefined) {
    contextLines.push(
      `- Days since last journal session: ${context.days_since_last}`
    );
  }
  if (context.session_count !== undefined) {
    contextLines.push(`- Total session count: ${context.session_count}`);
  }

  if (contextLines.length === 0) return CHAT_SYSTEM_PROMPT;

  return `${CHAT_SYSTEM_PROMPT}\n\nContext:\n${contextLines.join("\n")}`;
}

/**
 * Validate the incoming request body. Returns an error message or null if valid.
 */
function validateRequest(body: unknown): string | null {
  if (!body || typeof body !== "object") {
    return "Request body must be a JSON object";
  }

  const req = body as Record<string, unknown>;

  // Validate mode
  if (!req.mode || (req.mode !== "chat" && req.mode !== "metadata")) {
    return 'Field "mode" is required and must be "chat" or "metadata"';
  }

  // Validate messages array
  if (!Array.isArray(req.messages) || req.messages.length === 0) {
    return 'Field "messages" is required and must be a non-empty array';
  }

  // Validate each message has role and content
  for (let i = 0; i < req.messages.length; i++) {
    const msg = req.messages[i];
    if (!msg || typeof msg !== "object") {
      return `messages[${i}] must be an object`;
    }
    if (
      typeof msg.role !== "string" ||
      !["user", "assistant"].includes(msg.role)
    ) {
      return `messages[${i}].role must be "user" or "assistant"`;
    }
    if (typeof msg.content !== "string" || msg.content.length === 0) {
      return `messages[${i}].content must be a non-empty string`;
    }
  }

  return null;
}

/**
 * Create a structured error response. Never exposes internal details.
 */
function errorResponse(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

serve(async (req: Request) => {
  // Only accept POST requests
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  // --- Proxy secret check (prevents open-proxy abuse even in Phase 3) ---
  // The client sends the Supabase anon key as a Bearer token. We compare it
  // against the PROXY_ACCESS_KEY secret to verify the caller is our app.
  // Phase 4 upgrades this to full JWT validation.
  const authHeader = req.headers.get("Authorization");
  const proxyAccessKey = Deno.env.get("PROXY_ACCESS_KEY");
  if (!proxyAccessKey) {
    // Fail-closed: reject all requests if proxy secret is not configured
    console.error("PROXY_ACCESS_KEY not configured in Supabase secrets");
    return errorResponse("Service temporarily unavailable", 503);
  }
  const token = authHeader?.replace("Bearer ", "") ?? "";
  if (token !== proxyAccessKey) {
    return errorResponse("Unauthorized", 401);
  }
  // TODO Phase 4: Replace proxy secret with full JWT validation:
  // const jwt = authHeader?.replace("Bearer ", "") ?? "";
  // const isValid = await verifyJwt(jwt, Deno.env.get("SUPABASE_JWT_SECRET"));
  // if (!isValid) return errorResponse("Unauthorized", 401);

  // --- Payload size check ---
  const contentLength = req.headers.get("content-length");
  if (contentLength && parseInt(contentLength) > MAX_PAYLOAD_BYTES) {
    return errorResponse(
      `Payload too large. Maximum size is ${MAX_PAYLOAD_BYTES} bytes`,
      400
    );
  }

  // --- Parse and validate request body ---
  let body: RequestBody;
  try {
    const rawBody = await req.text();
    if (rawBody.length > MAX_PAYLOAD_BYTES) {
      return errorResponse(
        `Payload too large. Maximum size is ${MAX_PAYLOAD_BYTES} bytes`,
        400
      );
    }
    body = JSON.parse(rawBody);
  } catch {
    return errorResponse("Invalid JSON in request body", 400);
  }

  const validationError = validateRequest(body);
  if (validationError) {
    return errorResponse(validationError, 400);
  }

  // --- Get API key from Supabase secrets ---
  const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!apiKey) {
    // Log server-side for debugging, but never expose to client
    console.error("ANTHROPIC_API_KEY not configured in Supabase secrets");
    return errorResponse("Service temporarily unavailable", 503);
  }

  // --- Build system prompt based on mode ---
  const systemPrompt =
    body.mode === "chat"
      ? buildChatSystemPrompt(body.context)
      : METADATA_SYSTEM_PROMPT;

  // --- Call Claude API ---
  // Uses the Anthropic Messages API with the system parameter (not
  // concatenated into user messages — proper role separation per
  // security-specialist recommendation).
  try {
    const claudeResponse = await fetch(CLAUDE_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: CLAUDE_MODEL,
        max_tokens: MAX_TOKENS,
        system: systemPrompt,
        messages: body.messages,
      }),
    });

    if (!claudeResponse.ok) {
      const status = claudeResponse.status;
      // Map Claude API errors to client-safe messages
      if (status === 429) {
        return errorResponse("Rate limit exceeded. Please try again later.", 429);
      }
      if (status === 401 || status === 403) {
        console.error("Claude API authentication failed");
        return errorResponse("Service temporarily unavailable", 503);
      }
      console.error(`Claude API error: ${status}`);
      return errorResponse("AI service error. Please try again.", 502);
    }

    const claudeData: ClaudeResponse = await claudeResponse.json();

    // Extract text from Claude's response
    const responseText =
      claudeData.content
        ?.find((block) => block.type === "text")
        ?.text ?? "";

    if (!responseText) {
      return errorResponse("Empty response from AI service", 502);
    }

    // --- Build response based on mode ---
    if (body.mode === "metadata") {
      // For metadata mode, try to parse the response as JSON
      let metadata = null;
      let parseError: string | null = null;
      try {
        // Strip markdown code fences if present
        const cleaned = responseText
          .replace(/^```json?\s*/i, "")
          .replace(/```\s*$/, "")
          .trim();
        metadata = JSON.parse(cleaned);
      } catch {
        // Return a typed error code so the client can detect the failure
        // without leaking internals. The raw response is still returned
        // so the client can attempt its own parsing if desired.
        console.warn("Failed to parse metadata JSON from Claude response");
        parseError = "METADATA_PARSE_ERROR";
      }

      return new Response(
        JSON.stringify({
          response: responseText,
          metadata: metadata,
          ...(parseError ? { error_code: parseError } : {}),
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Chat mode — return the conversational response
    return new Response(
      JSON.stringify({
        response: responseText,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (error) {
    // Network error calling Claude API — never expose details
    console.error("Error calling Claude API:", error);
    return errorResponse("AI service unavailable. Please try again.", 502);
  }
});
