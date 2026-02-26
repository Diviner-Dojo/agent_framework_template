// ===========================================================================
// file: supabase/functions/elevenlabs-proxy/index.ts
// purpose: Supabase Edge Function that proxies ElevenLabs TTS API calls.
//          The ElevenLabs API key lives here as a secret, NEVER in the
//          mobile app (same pattern as claude-proxy, ADR-0005/ADR-0022).
//
// This function:
//   1. Receives text from the authenticated Flutter app
//   2. Calls the ElevenLabs text-to-speech API
//   3. Returns raw MP3 audio bytes
//
// Security:
//   - API key is in Deno.env (Supabase secret), never in response
//   - JWT validation via Supabase Auth + PROXY_ACCESS_KEY fallback
//   - Input validation: max 5000 character text limit
//   - Error responses never expose internal details or API key
//
// See: ADR-0022 (Voice Engine Swap)
// ===========================================================================

// @ts-ignore - Deno-specific import
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// @ts-ignore - Deno-specific import
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_TEXT_LENGTH = 5000;
const ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech";
const DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"; // "Sarah" — natural female
const DEFAULT_MODEL_ID = "eleven_turbo_v2_5";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RequestBody {
  text: string;
  voice_id?: string;
  model_id?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Validate the incoming request body. Returns an error message or null if valid.
 */
function validateRequest(body: unknown): string | null {
  if (!body || typeof body !== "object") {
    return "Request body must be a JSON object";
  }

  const req = body as Record<string, unknown>;

  if (typeof req.text !== "string" || req.text.length === 0) {
    return 'Field "text" is required and must be a non-empty string';
  }

  if (req.text.length > MAX_TEXT_LENGTH) {
    return `Text exceeds ${MAX_TEXT_LENGTH} character limit`;
  }

  if (req.voice_id !== undefined && typeof req.voice_id !== "string") {
    return 'Field "voice_id" must be a string';
  }

  if (req.model_id !== undefined && typeof req.model_id !== "string") {
    return 'Field "model_id" must be a string';
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

  // --- Auth: JWT validation with proxy secret fallback ---
  const authHeader = req.headers.get("Authorization");
  const token = authHeader?.replace("Bearer ", "") ?? "";

  let isAuthorized = false;

  // Try JWT validation via Supabase Auth
  if (token) {
    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY");

    if (supabaseUrl && supabaseAnonKey) {
      try {
        const supabase = createClient(supabaseUrl, supabaseAnonKey, {
          global: { headers: { Authorization: `Bearer ${token}` } },
        });
        const {
          data: { user },
          error,
        } = await supabase.auth.getUser();
        if (user && !error) {
          isAuthorized = true;
        }
      } catch {
        // JWT validation failed — fall through to proxy key check
      }
    }
  }

  // Fallback: proxy secret check
  if (!isAuthorized) {
    const proxyAccessKey = Deno.env.get("PROXY_ACCESS_KEY");
    if (!proxyAccessKey) {
      console.error("PROXY_ACCESS_KEY not configured in Supabase secrets");
      return errorResponse("Service temporarily unavailable", 503);
    }
    if (proxyAccessKey.length < 32) {
      console.error(
        "PROXY_ACCESS_KEY is too short — must be >= 32 characters"
      );
      return errorResponse("Service misconfigured", 503);
    }
    if (token !== proxyAccessKey) {
      return errorResponse("Unauthorized", 401);
    }
    isAuthorized = true;
  }

  // --- Parse and validate request body ---
  let body: RequestBody;
  try {
    body = await req.json();
  } catch {
    return errorResponse("Invalid JSON in request body", 400);
  }

  const validationError = validateRequest(body);
  if (validationError) {
    return errorResponse(validationError, 400);
  }

  // --- Get API key from Supabase secrets ---
  const apiKey = Deno.env.get("ELEVENLABS_API_KEY");
  if (!apiKey) {
    console.error("ELEVENLABS_API_KEY not configured in Supabase secrets");
    return errorResponse("Service temporarily unavailable", 503);
  }

  // --- Call ElevenLabs TTS API ---
  const voiceId = body.voice_id || DEFAULT_VOICE_ID;
  const modelId = body.model_id || DEFAULT_MODEL_ID;

  try {
    const ttsResponse = await fetch(`${ELEVENLABS_API_URL}/${voiceId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "xi-api-key": apiKey,
      },
      body: JSON.stringify({
        text: body.text,
        model_id: modelId,
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75,
        },
      }),
    });

    if (!ttsResponse.ok) {
      const status = ttsResponse.status;
      if (status === 429) {
        return errorResponse(
          "Rate limit exceeded. Please try again later.",
          429
        );
      }
      if (status === 401 || status === 403) {
        console.error("ElevenLabs API authentication failed");
        return errorResponse("Service temporarily unavailable", 503);
      }
      console.error(`ElevenLabs API error: ${status}`);
      return errorResponse("TTS service error. Please try again.", 502);
    }

    // Return raw audio bytes with appropriate content type
    const audioBytes = await ttsResponse.arrayBuffer();
    return new Response(audioBytes, {
      status: 200,
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": audioBytes.byteLength.toString(),
      },
    });
  } catch (error) {
    console.error("Error calling ElevenLabs API:", error);
    return errorResponse("TTS service unavailable. Please try again.", 502);
  }
});
