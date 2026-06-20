import { NextRequest, NextResponse } from "next/server";

// Server-side proxy for the A2A JSON-RPC SendMessage call. The browser posts
// {skill, message, token?, baseUrl?} here; we build the A2A envelope and call
// the backend server-side, so there are no CORS constraints and the bearer
// token never has to be embedded in client JS.

const DEFAULT_BASE = process.env.A2A_BACKEND_URL || "http://localhost:8000";

export async function POST(req: NextRequest) {
  let body: { skill?: string; message?: string; token?: string; baseUrl?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "JSON non valido" }, { status: 400 });
  }

  const skill = (body.skill || "search_open_data").trim();
  const message = (body.message || "").trim();
  if (!message) {
    return NextResponse.json({ error: "Il messaggio è vuoto" }, { status: 400 });
  }

  const base = (body.baseUrl?.trim() || DEFAULT_BASE).replace(/\/+$/, "");
  const url = `${base}/a2a/`;

  // A2A SDK 1.0 envelope (PascalCase method, ROLE_USER enum) — mirrors the
  // /docs/a2a example. The skill is selected via message.metadata.skill.
  const payload = {
    jsonrpc: "2.0",
    id: crypto.randomUUID(),
    method: "SendMessage",
    params: {
      message: {
        messageId: crypto.randomUUID(),
        role: "ROLE_USER",
        parts: [{ text: message }],
        metadata: { skill },
      },
    },
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "A2A-Version": "1.0",
  };
  const token = (body.token || process.env.A2A_BEARER || "").trim();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      // A2A analyses can run for minutes; don't let the proxy give up early.
      signal: AbortSignal.timeout(600_000),
    });
    const text = await resp.text();
    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      json = { raw: text };
    }
    return NextResponse.json(
      { ok: resp.ok, status: resp.status, sent: payload, result: json },
      { status: 200 },
    );
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err), target: url },
      { status: 502 },
    );
  }
}
