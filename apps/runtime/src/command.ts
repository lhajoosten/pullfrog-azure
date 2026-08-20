import { parseRuntimeConfig, RuntimeConfigurationError } from "./config.js";

export interface CommandIo {
  readonly stdout: (message: string) => void;
  readonly stderr: (message: string) => void;
}

export function runCommand(
  arguments_: readonly string[],
  environment: NodeJS.ProcessEnv,
  io: CommandIo,
): number {
  if (arguments_.length !== 1 || arguments_[0] !== "validate-config") {
    io.stderr("Usage: pullfrog-azure-runtime validate-config\n");
    return 2;
  }

  try {
    parseRuntimeConfig(environment);
  } catch (error: unknown) {
    if (!(error instanceof RuntimeConfigurationError)) {
      throw error;
    }

    io.stderr("Runtime configuration is invalid\n");
    return 2;
  }

  io.stdout("Runtime configuration is valid\n");
  return 0;
}
