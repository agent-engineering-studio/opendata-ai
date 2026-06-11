"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Legacy route → /esplora. Client-side redirect because static export has no
// server-side runtime to issue a 308.
export default function Page() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/esplora");
  }, [router]);
  return (
    <div className="container py-5">
      <p className="text-muted small">Reindirizzamento a /esplora…</p>
    </div>
  );
}
