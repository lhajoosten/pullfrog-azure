import { createApiClient } from "@pullfrog-azure/api-client";

export const apiClient = createApiClient(
  import.meta.env.VITE_API_BASE_URL ?? "",
);
