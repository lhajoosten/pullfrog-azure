import { createApiClient } from "@pullfrog-azure/api-client";
import { useQuery } from "@tanstack/react-query";

const client = createApiClient(import.meta.env.VITE_API_BASE_URL ?? "");

export function useLiveness() {
  return useQuery({
    queryKey: ["health", "live"],
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/health/live");
      if (error !== undefined || data === undefined) {
        throw new Error("Control plane is unavailable");
      }
      return data;
    },
  });
}
