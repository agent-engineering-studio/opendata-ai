"use client";

import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { proxyFetch } from "./api";

type State<T> =
  | { status: "loading" }
  | { status: "ok"; data: T; magic: string | null }
  | { status: "error"; message: string };

export function useProxyFetch<T>(
  url: string,
  decode: (resp: Response) => Promise<T>,
): State<T> {
  const [state, setState] = useState<State<T>>({ status: "loading" });
  const { getToken } = useAuth();

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });

    (async () => {
      try {
        // Use the getToken callback (not a pre-resolved token): previews
        // sometimes mount well after the chat stream completed and a static
        // token captured earlier may be expired.
        const resp = await proxyFetch(url, { getToken, signal: controller.signal });
        if (!resp.ok) {
          let detail = `HTTP ${resp.status}`;
          try {
            const j = (await resp.json()) as { error?: string };
            if (j.error) detail = j.error;
          } catch {
            /* keep default */
          }
          setState({ status: "error", message: detail });
          return;
        }
        const magic = resp.headers.get("x-binary-magic");
        const data = await decode(resp);
        setState({ status: "ok", data, magic });
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const message = err instanceof Error ? err.message : String(err);
        setState({ status: "error", message });
      }
    })();

    return () => controller.abort();
  }, [url, decode, getToken]);

  return state;
}
