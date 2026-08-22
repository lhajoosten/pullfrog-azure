import { useQuery } from "@tanstack/react-query";

import { apiClient } from "./client";

export const AUTH_SESSION_QUERY_KEY = ["auth", "session"] as const;

export function useAdminSession() {
  return useQuery({
    queryKey: AUTH_SESSION_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      try {
        const result = await apiClient.GET("/api/v1/auth/me");
        if (result.response.status === 401) {
          return null;
        }
        if (result.error !== undefined || result.data === undefined) {
          throw new Error("Admin session is unavailable");
        }
        return result.data;
      } catch {
        throw new Error("Admin session is unavailable");
      }
    },
  });
}
