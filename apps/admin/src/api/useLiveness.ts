import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";

export function useLiveness() {
  return useQuery({
    queryKey: ["health", "live"],
    queryFn: async () => {
      const { data, error } = await apiClient.GET("/api/v1/health/live");
      if (error !== undefined || data === undefined) {
        throw new Error("Control plane is unavailable");
      }
      return data;
    },
  });
}
