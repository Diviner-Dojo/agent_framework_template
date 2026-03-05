// ===========================================================================
// file: supabase/functions/deepgram-proxy/index.ts
// purpose: Supabase Edge Function that proxies Deepgram Nova-2 streaming STT
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
// Deepgram WebSocket auth (ADR-0031 addendum):
//   Deepgram does NOT accept permanent API keys via the `?token=` query
//   parameter for WebSocket streaming (returns 401). This is by design —
//   permanent keys should only be sent in Authorization headers (server-side).
//   Deno Deploy's built-in WebSocket does not support custom headers, and
//   npm:ws browser.js silently re-exports globalThis.WebSocket (dropping headers).
//
//   Solution: use Deepgram's temporary-credential API (server-side REST call)
//   to mint a short-lived token scoped to `usage:write`. Short-lived tokens
//   ARE accepted via `?token=` for WebSocket streaming — this is Deepgram's
//   official pattern for environments that cannot send Authorization headers.
//
//   Flow per connection:
//     1. GET /v1/projects → get projectId (one-time caches projectId)
//     2. POST /v1/projects/{id}/keys → mint 30s token with usage:write scope
//     3. Connect WebSocket: wss://api.deepgram.com/v1/listen?token=<temp>&params
//
// Diagnostic endpoint (GET):
//   A GET request (not WebSocket) tests the DEEPGRAM_API_KEY via Deepgram's
//   REST API and reports key validity + project count.
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
  "model=nova-2",              // nova-2: broadly available on all account tiers
  "language=en-US",
  "encoding=linear16",
  "sample_rate=16000",
  "channels=1",
  "endpointing=2000",          // 2000ms silence → speech_final fires
  "utterance_end_ms=1500",     // 1500ms silence → UtteranceEnd fallback
  "interim_results=true",      // Stream partials for responsive UI
  "vad_events=true",           // Voice activity detection events
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
// Deepgram temporary-credential helpers
// ---------------------------------------------------------------------------

/** Fetch the first Deepgram project ID associated with [apiKey]. */
async function getDeepgramProjectId(apiKey: string): Promise<string | null> {
  const resp = await fetch("https://api.deepgram.com/v1/projects", {
    headers: { Authorization: `Token ${apiKey}` },
  });
  if (!resp.ok) {
    console.error(`GET /projects failed: ${resp.status}`);
    return null;
  }
  const data = await resp.json() as { projects?: { project_id: string }[] };
  return data.projects?.[0]?.project_id ?? null;
}

/**
 * Obtain a short-lived Deepgram streaming token via POST /v1/auth/grant.
 * This is the correct endpoint for generating tokens used with the
 * `?token=` WebSocket query param. It returns a JWT-style ephemeral token
 * (not an API key) that Deepgram's streaming endpoint accepts.
 * POST /projects/{id}/keys creates sub-API-keys, which are NOT accepted
 * via `?token=` for WebSocket — only /auth/grant tokens are.
 */
async function mintDeepgramStreamToken(
  apiKey: string,
): Promise<{ token: string | null; responseKeys: string[]; status: number }> {
  const resp = await fetch(
    "https://api.deepgram.com/v1/auth/grant",
    {
      method: "POST",
      headers: {
        Authorization: `Token ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ttl_seconds: 30 }),
    },
  );
  const status = resp.status;
  if (!resp.ok) {
    const body = await resp.text();
    console.error(`POST /auth/grant failed: ${status} ${body}`);
    return { token: null, responseKeys: [], status };
  }
  // deno-lint-ignore no-explicit-any
  const data = await resp.json() as Record<string, any>;
  console.log(`POST /auth/grant response fields: ${Object.keys(data).join(", ")}`);
  // Deepgram returns { "access_token": "..." } from /auth/grant.
  const token =
    (typeof data["access_token"] === "string" ? data["access_token"] : null) ??
    (typeof data["token"] === "string" ? data["token"] : null) ??
    (typeof data["key"] === "string" ? data["key"] : null) ??
    null;
  return { token, responseKeys: Object.keys(data), status };
}

// ---------------------------------------------------------------------------
// Diagnostic helper — tests the Deepgram API key via REST
// ---------------------------------------------------------------------------

async function handleDiagnostic(req: Request): Promise<Response> {
  if (!(await isAuthorized(req))) {
    return jsonError("Unauthorized", 401);
  }

  const deepgramApiKey = Deno.env.get("DEEPGRAM_API_KEY");
  if (!deepgramApiKey) {
    return new Response(
      JSON.stringify({ ok: false, reason: "DEEPGRAM_API_KEY secret not set" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const resp = await fetch("https://api.deepgram.com/v1/projects", {
      headers: { Authorization: `Token ${deepgramApiKey}` },
    });
    const body = await resp.json().catch(() => ({})) as {
      projects?: { project_id: string }[];
    };
    const projectId = body.projects?.[0]?.project_id ?? null;

    // Also try minting an ephemeral streaming token via /auth/grant.
    let tempTokenOk = false;
    let mintStatus = 0;
    let mintResponseKeys: string[] = [];
    if (resp.ok) {
      const result = await mintDeepgramStreamToken(deepgramApiKey);
      tempTokenOk = result.token !== null;
      mintStatus = result.status;
      mintResponseKeys = result.responseKeys;
    }

    return new Response(
      JSON.stringify({
        ok: resp.ok,
        deepgramStatus: resp.status,
        projects: body.projects?.length ?? 0,
        projectId,
        streamingTokenOk: tempTokenOk,
        mintStatus,
        mintResponseKeys,
        keyPrefix: deepgramApiKey.substring(0, 8) + "...",
        model: "nova-2",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ ok: false, reason: `Deepgram check failed: ${e}` }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

serve(async (req: Request) => {
  // Non-WebSocket GET request: run diagnostic.
  const upgradeHeader = req.headers.get("upgrade") ?? "";
  if (upgradeHeader.toLowerCase() !== "websocket") {
    if (req.method === "GET") {
      return handleDiagnostic(req);
    }
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

  // Upgrade the incoming connection to WebSocket FIRST (Deno requirement:
  // must be called synchronously before any async work).
  const { socket: clientSocket, response } = Deno.upgradeWebSocket(req);

  // Pending audio queue: messages received from client before Deepgram
  // WebSocket is open. Drained once Deepgram onopen fires.
  const pendingAudio: (string | ArrayBuffer)[] = [];
  let deepgramSocket: WebSocket | null = null;

  clientSocket.onopen = async () => {
    // Mint a short-lived Deepgram token for WebSocket auth.
    // Permanent API keys return 401 via ?token= query param.
    // Short-lived tokens with usage:write scope are accepted.
    let streamToken: string | null = null;
    try {
      const result = await mintDeepgramStreamToken(deepgramApiKey);
      streamToken = result.token;
      if (!streamToken) {
        console.error(`Token mint returned no token. Status=${result.status} fields=${result.responseKeys.join(",")}`);
      }
    } catch (e) {
      console.error(`Failed to mint Deepgram stream token: ${e}`);
    }

    if (!streamToken) {
      console.error("Could not obtain Deepgram stream token — closing client.");
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.close(1011, "Deepgram token mint failed");
      }
      return;
    }

    // Use ?access_token= (not ?token=) for tokens from /v1/auth/grant.
    // Deepgram's /auth/grant returns OAuth-style { "access_token": "..." }.
    // The matching WebSocket URL parameter is ?access_token=<TOKEN>.
    // The ?token= parameter is for sub-API-keys from POST /projects/{id}/keys,
    // NOT for OAuth access tokens — using ?token= with /auth/grant returns 401.
    const deepgramUrl =
      `${DEEPGRAM_BASE_URL}?access_token=${streamToken}&${DEEPGRAM_PARAMS}`;

    deepgramSocket = new WebSocket(deepgramUrl);

    deepgramSocket.onopen = () => {
      console.log("Deepgram WebSocket opened (short-lived token auth)");
      for (const chunk of pendingAudio) {
        deepgramSocket!.send(chunk);
      }
      pendingAudio.length = 0;
    };

    deepgramSocket.onmessage = (event) => {
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.send(event.data);
      }
    };

    deepgramSocket.onclose = (event) => {
      console.log(`Deepgram closed: code=${event.code} reason=${event.reason}`);
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.close(event.code, event.reason || "Deepgram closed");
      }
    };

    deepgramSocket.onerror = (error) => {
      const msg = (error as ErrorEvent).message || "unknown";
      console.error(`Deepgram WebSocket error: ${msg}`);
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.close(1011, `Deepgram error: ${msg}`);
      }
    };
  };

  clientSocket.onmessage = (event) => {
    if (deepgramSocket !== null && deepgramSocket.readyState === WebSocket.OPEN) {
      deepgramSocket.send(event.data);
    } else {
      if (pendingAudio.length >= MAX_PENDING_AUDIO) {
        pendingAudio.shift();
      }
      pendingAudio.push(event.data);
    }
  };

  clientSocket.onclose = () => {
    if (deepgramSocket !== null && deepgramSocket.readyState === WebSocket.OPEN) {
      try {
        deepgramSocket.send(JSON.stringify({ type: "CloseStream" }));
      } catch {
        // Best-effort.
      }
      deepgramSocket.close(1000, "Client disconnected");
    }
  };

  clientSocket.onerror = (error) => {
    console.error("Client WebSocket error:", error);
    if (deepgramSocket !== null && deepgramSocket.readyState === WebSocket.OPEN) {
      deepgramSocket.close(1011, "Client error");
    }
  };

  return response;
});
