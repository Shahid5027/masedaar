import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3015",
    channel: "chrome",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: ".venv\\Scripts\\python.exe scripts\\e2e_server.py",
      cwd: "..",
      url: "http://127.0.0.1:8015/api/ps3/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm.cmd run start -- -H 127.0.0.1 -p 3015",
      cwd: ".",
      url: "http://127.0.0.1:3015/login",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

