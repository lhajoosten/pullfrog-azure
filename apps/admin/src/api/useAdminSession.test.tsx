import type { PropsWithChildren } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAdminSession } from "./useAdminSession";

const client = vi.hoisted(() => ({ GET: vi.fn() }));

vi.mock("./client", () => ({ apiClient: client }));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useAdminSession", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps an unauthenticated response to an anonymous session", async () => {
    client.GET.mockResolvedValue({
      data: undefined,
      error: { error: "invalid_session" },
      response: new Response(null, { status: 401 }),
    });

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/auth/me");
  });

  it("throws fixed copy for non-401 failures", async () => {
    client.GET.mockResolvedValue({
      data: undefined,
      error: { detail: "provider-secret-marker" },
      response: new Response(null, { status: 503 }),
    });

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("Admin session is unavailable"),
    );
    expect(String(result.current.error)).not.toContain(
      "provider-secret-marker",
    );
  });

  it("replaces thrown transport details with fixed copy", async () => {
    client.GET.mockRejectedValue(new Error("provider-secret-marker"));

    const { result } = renderHook(() => useAdminSession(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toEqual(
      new Error("Admin session is unavailable"),
    );
    expect(String(result.current.error)).not.toContain(
      "provider-secret-marker",
    );
  });
});
