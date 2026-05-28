import { NextRequest, NextResponse } from "next/server";

const MAX_BYTES = 15 * 1024 * 1024; // 15 MB cap (PDFs can be a few MB)
const TIMEOUT_MS = 25_000;

const BINARY_MAGIC: Array<[number[], string]> = [
  [[0x50, 0x4b, 0x03, 0x04], "ZIP"],
  [[0x50, 0x4b, 0x05, 0x06], "ZIP"],
  [[0x50, 0x4b, 0x07, 0x08], "ZIP"],
  [[0x1f, 0x8b], "GZIP"],
  [[0x25, 0x50, 0x44, 0x46], "PDF"],
  [[0xd0, 0xcf, 0x11, 0xe0], "OLE2"],
  [[0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c], "7Z"],
];

function detectMagic(buf: Uint8Array): string | null {
  for (const [sig, name] of BINARY_MAGIC) {
    if (buf.length < sig.length) continue;
    let match = true;
    for (let i = 0; i < sig.length; i++) {
      if (buf[i] !== sig[i]) {
        match = false;
        break;
      }
    }
    if (match) return name;
  }
  return null;
}

export const runtime = "nodejs";

export async function GET(req: NextRequest): Promise<NextResponse> {
  const target = req.nextUrl.searchParams.get("url");
  if (!target) {
    return NextResponse.json({ error: "Missing 'url' query parameter" }, { status: 400 });
  }

  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return NextResponse.json({ error: "Invalid URL" }, { status: 400 });
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return NextResponse.json({ error: "Only http(s) URLs are allowed" }, { status: 400 });
  }

  try {
    const upstream = await fetch(parsed.toString(), {
      redirect: "follow",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!upstream.ok) {
      return NextResponse.json(
        { error: `Upstream ${upstream.status} ${upstream.statusText}` },
        { status: 502 },
      );
    }

    const contentLength = Number(upstream.headers.get("content-length") ?? "0");
    if (contentLength && contentLength > MAX_BYTES) {
      return NextResponse.json(
        { error: `Resource too large (${contentLength} bytes, cap ${MAX_BYTES})` },
        { status: 413 },
      );
    }

    const arrayBuf = await upstream.arrayBuffer();
    if (arrayBuf.byteLength > MAX_BYTES) {
      return NextResponse.json(
        { error: `Resource too large (${arrayBuf.byteLength} bytes, cap ${MAX_BYTES})` },
        { status: 413 },
      );
    }

    const body = new Uint8Array(arrayBuf);
    const magic = detectMagic(body);

    const headers = new Headers();
    const upstreamType = upstream.headers.get("content-type");
    if (upstreamType) headers.set("content-type", upstreamType);
    if (magic) headers.set("x-binary-magic", magic);
    headers.set("cache-control", "private, max-age=60");

    return new NextResponse(body, { status: 200, headers });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const isTimeout = message.toLowerCase().includes("timeout");
    return NextResponse.json(
      { error: isTimeout ? `Timeout dopo ${TIMEOUT_MS / 1000}s` : `Errore di rete: ${message}` },
      { status: 502 },
    );
  }
}
