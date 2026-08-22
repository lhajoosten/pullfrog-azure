import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "./client";
import { AUTH_SESSION_QUERY_KEY } from "./useAdminSession";

const CSRF_COOKIE = "pullfrog_admin_csrf";

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  const encoded = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(prefix))
    ?.slice(prefix.length);
  if (encoded === undefined || encoded === "") {
    return null;
  }
  try {
    return decodeURIComponent(encoded);
  } catch {
    return null;
  }
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      try {
        const csrfToken = readCookie(CSRF_COOKIE);
        if (csrfToken === null) {
          throw new Error("Admin logout is unavailable");
        }
        const result = await apiClient.POST("/api/v1/auth/logout", {
          params: { header: { "X-Pullfrog-CSRF": csrfToken } },
        });
        if (!result.response.ok || result.error !== undefined) {
          throw new Error("Admin logout is unavailable");
        }
      } catch {
        throw new Error("Admin logout is unavailable");
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: AUTH_SESSION_QUERY_KEY });
    },
  });
}
