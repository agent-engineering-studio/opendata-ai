import { NextRequest, NextResponse } from "next/server";
import type { ChatRequest, ChatResponse } from "@/lib/types";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://localhost:8000";
// Local multi-agent queries on a large Ollama model (e.g. qwen2.5:32b) can take
// several minutes (3 sequential LLM calls + SDMX catalogue fetch). Default 10 min
// so slow local replies aren't aborted; lower it for fast cloud providers.
const TIMEOUT_MS = Number(process.env.AGENT_API_TIMEOUT_MS ?? 600_000);

export const runtime = "nodejs";

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: ChatRequest;
  try {
    body = (await req.json()) as ChatRequest;
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON in request body" },
      { status: 400 },
    );
  }

  if (!body?.query || typeof body.query !== "string") {
    return NextResponse.json(
      { error: "Missing 'query' field" },
      { status: 400 },
    );
  }

  const upstreamUrl = `${AGENT_API_URL.replace(/\/$/, "")}/chat`;

  try {
    const upstream = await fetch(upstreamUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });

    const text = await upstream.text();

    if (!upstream.ok) {
      const excerpt = text.slice(0, 500);
      console.error(
        `[api/chat] upstream ${upstream.status} ${upstream.statusText}: ${excerpt}`,
      );
      return NextResponse.json(
        {
          error: `Backend ${upstream.status}: ${excerpt || upstream.statusText}`,
        },
        { status: 502 },
      );
    }

    let json: ChatResponse;
    try {
      json = JSON.parse(text) as ChatResponse;
    } catch {
      console.error(
        `[api/chat] upstream returned non-JSON body:`,
        text.slice(0, 500),
      );
      return NextResponse.json(
        { error: "Backend returned a non-JSON response" },
        { status: 502 },
      );
    }

    return NextResponse.json(json, { status: 200 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const isTimeout = message.toLowerCase().includes("timeout");
    console.error(`[api/chat] transport error:`, err);
    return NextResponse.json(
      {
        error: isTimeout
          ? `Timeout dopo ${TIMEOUT_MS / 1000}s — l'agent non ha risposto in tempo`
          : `Backend non raggiungibile: ${message}`,
      },
      { status: 502 },
    );
  }
}
