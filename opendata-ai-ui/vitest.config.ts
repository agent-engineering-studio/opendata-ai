import { resolve } from "node:path";

import { defineConfig } from "vitest/config";

// Test unitari su moduli puri (no DOM): environment node di default.
// Replica l'alias `@/*` → root di tsconfig.json così gli import dei moduli
// sotto test si risolvono come in build.
export default defineConfig({
  resolve: {
    alias: { "@": resolve(__dirname, ".") },
  },
  test: {
    include: ["lib/**/*.test.ts"],
  },
});
