import type { PropsWithChildren } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLogout } from "./useLogout";

const client = vi.hoisted(() => ({ POST: vi.fn() }));

vi.mock("./client", () => ({ apiClient: client }));

function expireBrowserCookies() {
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.split("=", 1)[0]?.trim();
    if (name !== undefined && name !== "") {
      document.cookie = `${name}=; Max-Age=0; Path=/`;
    }
  }
}

function createHarness() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false } },
  });
  const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  return { invalidateQueries, Wrapper };
}

describe("useLogout", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    expireBrowserCookies();
  });

  it("decodes the exact CSRF cookie and invalidates the session query", async () => {
    document.cookie = "unrelated=value; Path=/";
    document.cookie = "pullfrog_admin_csrf=safe%2Bproof%3D; Path=/";
    client.POST.mockResolvedValue({
      data: undefined,
      error: undefined,
      response: new Response(null, { status: 204 }),
    });
    const { invalidateQueries, Wrapper } = createHarness();
    const { result } = renderHook(() => useLogout(), { wrapper: Wrapper });

    act(() => result.current.mutate());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.POST).toHaveBeenCalledWith("/api/v1/auth/logout", {
      params: { header: { "X-Pullfrog-CSRF": "safe+proof=" } },
    });
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["auth", "session"],
    });
  });

  it("fails locally with fixed copy when the CSRF cookie is missing", async () => {
    const { Wrapper } = createHarness();
    const { result } = renderHook(() => useLogout(), { wrapper: Wrapper });

    act(() => result.current.mutate());

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("Admin logout is unavailable"),
    );
    expect(client.POST).not.toHaveBeenCalled();
  });

  it("rejects a malformed encoded CSRF cookie without forwarding it", async () => {
    document.cookie = "pullfrog_admin_csrf=%E0%A4%A; Path=/";
    const { Wrapper } = createHarness();
    const { result } = renderHook(() => useLogout(), { wrapper: Wrapper });

    act(() => result.current.mutate());

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("Admin logout is unavailable"),
    );
    expect(client.POST).not.toHaveBeenCalled();
  });

  it("replaces thrown transport details with fixed copy", async () => {
    document.cookie = "pullfrog_admin_csrf=safe-proof; Path=/";
    client.POST.mockRejectedValue(new Error("provider-secret-marker"));
    const { Wrapper } = createHarness();
    const { result } = renderHook(() => useLogout(), { wrapper: Wrapper });

    act(() => result.current.mutate());

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("Admin logout is unavailable"),
    );
    expect(String(result.current.error)).not.toContain(
      "provider-secret-marker",
    );
  });
});
