import { describe, expect, it } from "vitest";

import { runCommand } from "./command.js";

function validEnvironment(): NodeJS.ProcessEnv {
  return {
    PULLFROG_CONTROL_PLANE_URL: "https://pullfrog.example.test",
    PULLFROG_RUN_ID: "c70a2290-df31-4fb8-81da-140f92c84031",
    PULLFROG_BOOTSTRAP_TOKEN: "a".repeat(48),
  };
}

function commandIo() {
  const stdout: string[] = [];
  const stderr: string[] = [];

  return {
    stdout,
    stderr,
    io: {
      stdout: (message: string): void => {
        stdout.push(message);
      },
      stderr: (message: string): void => {
        stderr.push(message);
      },
    },
  };
}

describe("runCommand", () => {
  it("validates configuration with exact success output", () => {
    const { io, stderr, stdout } = commandIo();

    const exitCode = runCommand(["validate-config"], validEnvironment(), io);

    expect(exitCode).toBe(0);
    expect(stdout).toEqual(["Runtime configuration is valid\n"]);
    expect(stderr).toEqual([]);
  });

  it("reports invalid configuration without exposing the supplied token", () => {
    const token = "visible-token-that-must-never-leak";
    const { io, stderr, stdout } = commandIo();

    const exitCode = runCommand(
      ["validate-config"],
      { PULLFROG_BOOTSTRAP_TOKEN: token },
      io,
    );

    expect(exitCode).toBe(2);
    expect(stdout).toEqual([]);
    expect(stderr).toEqual(["Runtime configuration is invalid\n"]);
    expect([...stdout, ...stderr].join("")).not.toContain(token);
  });

  it("reports exact usage for an unsupported invocation", () => {
    const { io, stderr, stdout } = commandIo();

    const exitCode = runCommand([], validEnvironment(), io);

    expect(exitCode).toBe(2);
    expect(stdout).toEqual([]);
    expect(stderr).toEqual(["Usage: pullfrog-azure-runtime validate-config\n"]);
  });

  it("does not catch unexpected programmer errors", () => {
    const unexpectedError = new Error("unexpected programmer error");
    const environment: NodeJS.ProcessEnv = {};
    Object.defineProperty(environment, "PULLFROG_CONTROL_PLANE_URL", {
      enumerable: true,
      get(): string {
        throw unexpectedError;
      },
    });
    const { io, stderr, stdout } = commandIo();

    expect(() => runCommand(["validate-config"], environment, io)).toThrow(
      unexpectedError,
    );
    expect(stdout).toEqual([]);
    expect(stderr).toEqual([]);
  });
});
