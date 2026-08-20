/** @vitest-environment node */

import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

import { createServer as createViteServer, type ViteDevServer } from "vite";
import { describe, expect, it } from "vitest";

function listen(server: Server, port: number): Promise<void> {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      server.off("error", reject);
      resolve();
    });
  });
}

function close(server: Server): Promise<void> {
  return new Promise((resolve, reject) => {
    server.close((error) => {
      if (error === undefined) {
        resolve();
        return;
      }
      reject(error);
    });
  });
}

function listeningPort(server: {
  address(): string | AddressInfo | null;
}): number {
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("Vite did not bind a TCP port");
  }
  return address.port;
}

describe("local API proxy", () => {
  it("forwards same-origin liveness requests to the local control plane", async () => {
    const controlPlane = createServer((request, response) => {
      if (request.url !== "/api/v1/health/live") {
        response.writeHead(404).end();
        return;
      }

      response.writeHead(200, { "content-type": "application/json" });
      response.end('{"status":"ok"}');
    });
    let vite: ViteDevServer | undefined;

    await listen(controlPlane, 8000);
    try {
      vite = await createViteServer({
        server: { host: "127.0.0.1", port: 0 },
      });
      await vite.listen();

      const viteServer = vite.httpServer;
      if (viteServer === null) {
        throw new Error("Vite development server is unavailable");
      }

      const response = await fetch(
        `http://127.0.0.1:${listeningPort(viteServer)}/api/v1/health/live`,
      );

      expect(response.status).toBe(200);
      expect(response.headers.get("content-type")).toContain(
        "application/json",
      );
      await expect(response.json()).resolves.toEqual({ status: "ok" });
    } finally {
      if (vite !== undefined) {
        await vite.close();
      }
      await close(controlPlane);
    }
  });
});
