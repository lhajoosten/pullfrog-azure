import { z } from "zod";

export interface RuntimeConfig {
  readonly controlPlaneUrl: URL;
  readonly runId: string;
  readonly bootstrapToken: string;
}

export class RuntimeConfigurationError extends Error {
  public constructor() {
    super("Runtime configuration is invalid");
    this.name = "RuntimeConfigurationError";
  }
}

const runtimeEnvironmentSchema = z.object({
  PULLFROG_CONTROL_PLANE_URL: z
    .string()
    .url()
    .refine(
      (value) => URL.canParse(value) && new URL(value).protocol === "https:",
    ),
  PULLFROG_RUN_ID: z.string().uuid(),
  PULLFROG_BOOTSTRAP_TOKEN: z.string().min(32),
});

export function parseRuntimeConfig(
  environment: NodeJS.ProcessEnv,
): RuntimeConfig {
  const result = runtimeEnvironmentSchema.safeParse(environment);
  if (!result.success) {
    throw new RuntimeConfigurationError();
  }

  return {
    controlPlaneUrl: new URL(result.data.PULLFROG_CONTROL_PLANE_URL),
    runId: result.data.PULLFROG_RUN_ID,
    bootstrapToken: result.data.PULLFROG_BOOTSTRAP_TOKEN,
  };
}
