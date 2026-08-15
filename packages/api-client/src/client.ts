import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./schema.js";

export function createApiClient(baseUrl: string): Client<paths> {
  return createClient<paths>({ baseUrl });
}
