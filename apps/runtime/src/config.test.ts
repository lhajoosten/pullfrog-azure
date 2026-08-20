import { describe, expect, it } from "vitest";

import { parseRuntimeConfig } from "./config.js";

describe("parseRuntimeConfig", () => {
  it("parses a valid run-scoped configuration", () => {
    const config = parseRuntimeConfig({
      PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
      PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
      PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
    });

    expect(config.runId).toBe("c70a2290-df31-4fb8-81da-140f92c84031");
    expect(config.controlPlaneUrl.href).toBe("https://pullfrog.example.test/");
  });

  it("accepts a bootstrap token at the minimum length", () => {
    const config = parseRuntimeConfig({
      PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
      PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
      PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(32),
    });

    expect(config.bootstrapToken).toHaveLength(32);
  });

  it("rejects a non-HTTPS control-plane URL with the fixed validation error", () => {
    expect(() =>
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: "http://pullfrog.example.test",
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      }),
    ).toThrowError("Runtime configuration is invalid");
  });

  it("rejects a non-UUID run ID with the fixed validation error", () => {
    expect(() =>
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
        PULLFROG_RUN_ID: "not-a-run-id",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      }),
    ).toThrowError("Runtime configuration is invalid");
  });

  it("rejects a short bootstrap token with the fixed validation error", () => {
    expect(() =>
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(31),
      }),
    ).toThrowError("Runtime configuration is invalid");
  });

  it("never includes the supplied token in validation errors", () => {
    const token = "visible-token-that-must-never-leak";

    expect(() =>
      parseRuntimeConfig({ PULLFROG_BOOTSTRAP_TOKEN: token }),
    ).toThrowError("Runtime configuration is invalid");
    try {
      parseRuntimeConfig({ PULLFROG_BOOTSTRAP_TOKEN: token });
    } catch (error: unknown) {
      expect(String(error)).not.toContain(token);
    }
  });

  it("replaces malformed URL errors with the fixed validation error", () => {
    const malformedUrl = "https://[malformed";

    expect(() =>
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: malformedUrl,
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      }),
    ).toThrowError("Runtime configuration is invalid");

    try {
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: malformedUrl,
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      });
    } catch (error: unknown) {
      expect(String(error)).not.toContain(malformedUrl);
    }
  });

  it("never includes URL credentials in validation errors", () => {
    const credential = "credential-that-must-stay-private";

    expect(() =>
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: `https://runtime:${credential}@pullfrog.example.test`,
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      }),
    ).toThrowError("Runtime configuration is invalid");

    try {
      parseRuntimeConfig({
        PULLFROG_CONTROL_PLANE_URL: `https://runtime:${credential}@pullfrog.example.test`,
        PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
        PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
      });
    } catch (error: unknown) {
      expect(String(error)).toBe(
        "RuntimeConfigurationError: Runtime configuration is invalid",
      );
      expect(String(error)).not.toContain(credential);
    }
  });
});
