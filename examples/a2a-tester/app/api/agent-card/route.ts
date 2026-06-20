import { NextRequest, NextResponse } from "next/server";

// Fetches the public AgentCard server-side. The A2A SDK 1.0 path uses a dash
// (`agent-card.json`); we also try the legacy `agent.json` as a fallback.
const DEFAULT_BASE = process.env.A2A_BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const base = (req.nextUrl.searchParams.get("baseUrl")?.trim() || DEFAULT_BASE).replace(
    /\/+$/,
    "",
  );
  const candidates = [
    `${base}/.well-known/agent-card.json`,
    `${base}/.well-known/agent.json`,
  ];
  for (const url of candidates) {
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(15_000) });
      if (resp.ok) {
        return NextResponse.json({ ok: true, url, card: await resp.json() });
      }
    } catch {
      /* try next candidate */
    }
  }
  return NextResponse.json(
    { ok: false, error: "AgentCard non raggiungibile", tried: candidates },
    { status: 502 },
  );
}
