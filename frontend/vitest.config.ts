import path from "node:path";
import { defineConfig } from "vitest/config";

// Mirrors tsconfig's `@/*` alias so the auth-callback tests import the
// exact modules the app uses. Node environment only — these tests cover
// server-side Auth.js callback logic, no DOM involved.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
  },
});
