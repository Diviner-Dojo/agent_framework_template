// ===========================================================================
// file: supabase/functions/deepgram-proxy/index.ts
// purpose: Supabase Edge Function that proxies Deepgram Nova-3 streaming STT
//          via bidirectional WebSocket relay.
//
// Architecture (ADR-0031):
//   Client opens WebSocket → this proxy → Deepgram WebSocket
//   Audio bytes from client are forwarded verbatim to Deepgram.
//   Deepgram transcription JSON events are forwarded back to client.
//   No audio is buffered or stored server-side.
//
// Authentication:
//   - Supabase JWT (Bearer token from authenticated users), OR
//   - PROXY_ACCESS_KEY fallback (same as elevenlabs-proxy pattern)
//   The DEEPGRAM_API_KEY lives in Supabase secrets — never in client code.
//
// Deepgram URL auth:
//   Deepgram accepts API key via `access_token` query param for WebSocket
//   connections (standard Web API WebSocket constructor does not support
//   custom headers). This is safe for server-side code because:
//     1. The key is only present inside the Edge Function process — never
//        transmitted to the client or exposed via any API response.
//     2. The deepgramUrl string is never written to any log statement.
//     3. Edge Function logs are only accessible to the Supabase project admin.
//   If Deno adds stable WebSocket header support, migrate to Authorization header.
//
// See: ADR-0031, ADR-0005
// ===========================================================================

// @ts-ignore - Deno-specific import
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
// @ts-ignore - Deno-specific import
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Deepgram streaming config — journaling-tuned per ADR-0031
// ---------------------------------------------------------------------------

const DEEPGRAM_BASE_URL = "wss://api.deepgram.com/v1/listen";
// Hard cap on queued audio chunks before Deepgram opens.
// At 16kHz PCM16 mono, each ~20ms chunk ≈ 640 bytes → 100 chunks ≈ 2s of audio.
// Older chunks are dropped (oldest-first) to prevent unbounded memory growth.
const MAX_PENDING_AUDIO = 100;
const DEEPGRAM_PARAMS = [
  "model=nova-3",
  "language=en-US",
  "encoding=linear16",
  "sample_rate=16000",
  "channels=1",
  "endpointing=2000",        // 2000ms silence → speech_final fires
  "utterance_end_ms=1500",   // 1500ms silence → UtteranceEnd fallback
  "interim_results=true",    // Stream partials for responsive UI
  "vad_events=true",         // Voice activity detection events
].join("&");

// ---------------------------------------------------------------------------
// Auth helper
// ---------------------------------------------------------------------------

async function isAuthorized(req: Request): Promise<boolean> {
  const authHeader = req.headers.get("Authorization") ?? "";
  const token = authHeader.replace("Bearer ", "").trim();

  if (!token) return false;

  // Try Supabase JWT validation first.
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
      if (user && !error) return true;
    } catch {
      // JWT check failed — fall through to proxy key.
    }
  }

  // Fallback: match PROXY_ACCESS_KEY (same pattern as elevenlabs-proxy).
  const proxyAccessKey = Deno.env.get("PROXY_ACCESS_KEY");
  if (!proxyAccessKey || proxyAccessKey.length < 32) {
    console.error("PROXY_ACCESS_KEY not configured or too short");
    return false;
  }
  return token === proxyAccessKey;
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

function jsonError(message: string, status: number): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

serve(async (req: Request) => {
  // Only accept WebSocket upgrade requests.
  const upgradeHeader = req.headers.get("upgrade") ?? "";
  if (upgradeHeader.toLowerCase() !== "websocket") {
    return jsonError("Expected WebSocket upgrade", 400);
  }

  // Authenticate before upgrading.
  if (!(await isAuthorized(req))) {
    return jsonError("Unauthorized", 401);
  }

  // Get Deepgram API key from Supabase secrets.
  const deepgramApiKey = Deno.env.get("DEEPGRAM_API_KEY");
  if (!deepgramApiKey) {
    console.error("DEEPGRAM_API_KEY not configured in Supabase secrets");
    return jsonError("Service temporarily unavailable", 503);
  }

  // Upgrade the incoming connection to WebSocket.
  // Must be called synchronously before returning — Deno requirement.
  const { socket: clientSocket, response } = Deno.upgradeWebSocket(req);

  // Pending audio queue: messages received from client before Deepgram
  // WebSocket is open. Drained once Deepgram onopen fires.
  const pendingAudio: (string | ArrayBuffer)[] = [];
  let deepgramSocket: WebSocket | null = null;

  clientSocket.onopen = () => {
    // Build Deepgram URL with API key as query param (server-side only).
    const deepgramUrl =
      `${DEEPGRAM_BASE_URL}?access_token=${deepgramApiKey}&${DEEPGRAM_PARAMS}`;

    deepgramSocket = new WebSocket(deepgramUrl);

    deepgramSocket.onopen = () => {
      // Drain any audio buffered before Deepgram was ready.
      for (const chunk of pendingAudio) {
        deepgramSocket!.send(chunk);
      }
      pendingAudio.length = 0;
    };

    deepgramSocket.onmessage = (event) => {
      // Forward Deepgram transcription events to the client.
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.send(event.data);
      }
    };

    deepgramSocket.onclose = (event) => {
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.close(event.code, event.reason || "Deepgram closed");
      }
    };

    deepgramSocket.onerror = (error) => {
      console.error("Deepgram WebSocket error:", error);
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.close(1011, "Deepgram connection error");
      }
    };
  };

  clientSocket.onmessage = (event) => {
    if (
      deepgramSocket !== null &&
      deepgramSocket.readyState === WebSocket.OPEN
    ) {
      // Relay audio bytes or control messages to Deepgram.
      deepgramSocket.send(event.data);
    } else {
      // Deepgram not open yet — buffer audio (bounded queue, drop oldest).
      if (pendingAudio.length >= MAX_PENDING_AUDIO) {
        pendingAudio.shift(); // Discard oldest chunk to bound memory usage.
      }
      pendingAudio.push(event.data);
    }
  };

  clientSocket.onclose = () => {
    if (
      deepgramSocket !== null &&
      deepgramSocket.readyState === WebSocket.OPEN
    ) {
      // Send Deepgram's CloseStream signal for clean flush, then close.
      try {
        deepgramSocket.send(JSON.stringify({ type: "CloseStream" }));
      } catch {
        // Best-effort — ignore if already closing.
      }
      deepgramSocket.close(1000, "Client disconnected");
    }
  };

  clientSocket.onerror = (error) => {
    console.error("Client WebSocket error:", error);
    if (
      deepgramSocket !== null &&
      deepgramSocket.readyState === WebSocket.OPEN
    ) {
      deepgramSocket.close(1011, "Client error");
    }
  };

  return response;
});
