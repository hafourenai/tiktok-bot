import { defineConfig } from "oxfmt";

export const ignorePatterns = [
  ".github/**",
  "built/**",
  "src/handlers/index.ts",
  "test/resources/**",
];

export default defineConfig({ ignorePatterns });
