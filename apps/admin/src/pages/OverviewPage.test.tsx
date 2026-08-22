import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import OverviewPage from "./OverviewPage";

const hooks = vi.hoisted(() => ({
  useAdminSession: vi.fn(),
  useLiveness: vi.fn(),
  useLogout: vi.fn(),
}));

vi.mock("../api/useAdminSession", () => ({
  useAdminSession: hooks.useAdminSession,
}));
vi.mock("../api/useLiveness", () => ({ useLiveness: hooks.useLiveness }));
vi.mock("../api/useLogout", () => ({ useLogout: hooks.useLogout }));

const SESSION = {
  absolute_expires_at: "2026-08-21T20:00:00Z",
  display_name: "Ada Admin",
  idle_expires_at: "2026-08-21T12:30:00Z",
};

function anonymousSession() {
  hooks.useAdminSession.mockReturnValue({
    data: null,
    isError: false,
    isPending: false,
  });
}

function authenticatedSession(displayName: string | null = "Ada Admin") {
  hooks.useAdminSession.mockReturnValue({
    data: { ...SESSION, display_name: displayName },
    isError: false,
    isPending: false,
  });
}

describe("OverviewPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");
    hooks.useLogout.mockReturnValue({ isPending: false, mutate: vi.fn() });
    hooks.useLiveness.mockReturnValue({ isError: false, isPending: false });
  });

  it("shows sign in instead of the overview for an anonymous browser", () => {
    anonymousSession();

    render(<OverviewPage />);

    expect(
      screen.getByRole("link", { name: "Sign in with Microsoft" }),
    ).toHaveAttribute("href", "/api/v1/auth/login?return_to=%2F");
    expect(
      screen.queryByText("Control plane is reachable"),
    ).not.toBeInTheDocument();
    expect(hooks.useLiveness).not.toHaveBeenCalled();
  });

  it("shows a fixed loading state while the session is unresolved", () => {
    hooks.useAdminSession.mockReturnValue({
      data: undefined,
      isError: false,
      isPending: true,
    });

    render(<OverviewPage />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking administrator session",
    );
    expect(hooks.useLiveness).not.toHaveBeenCalled();
  });

  it("shows a fixed failure when the session query fails", () => {
    hooks.useAdminSession.mockReturnValue({
      data: undefined,
      isError: true,
      isPending: false,
    });

    render(<OverviewPage />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Administrator session is unavailable",
    );
    expect(hooks.useLiveness).not.toHaveBeenCalled();
  });

  it("renders the overview only for an authenticated administrator", () => {
    authenticatedSession();

    render(<OverviewPage />);

    expect(screen.getByText("Signed in as Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("Control plane is reachable")).toBeInTheDocument();
    expect(hooks.useLiveness).toHaveBeenCalledOnce();
  });

  it("does not invent a display name when Entra omitted it", () => {
    authenticatedSession(null);

    render(<OverviewPage />);

    expect(screen.getByText("Signed in")).toBeInTheDocument();
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
  });

  it("maps an allowlisted callback error to fixed copy", () => {
    anonymousSession();
    window.history.replaceState({}, "", "/?auth_error=identity_not_authorized");

    render(<OverviewPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This Microsoft account is not authorized.",
    );
  });

  it("uses generic copy for an unknown callback value without reflecting it", () => {
    anonymousSession();
    window.history.replaceState({}, "", "/?auth_error=provider-secret-marker");

    render(<OverviewPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Microsoft sign-in failed. Please try again.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent(
      "provider-secret-marker",
    );
  });

  it("disables logout while its mutation is pending", () => {
    authenticatedSession();
    hooks.useLogout.mockReturnValue({ isPending: true, mutate: vi.fn() });

    render(<OverviewPage />);

    expect(screen.getByRole("button", { name: "Signing out" })).toBeDisabled();
  });

  it("delegates a logout click to the mutation hook", () => {
    authenticatedSession();
    const mutate = vi.fn();
    hooks.useLogout.mockReturnValue({ isPending: false, mutate });

    render(<OverviewPage />);
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(mutate).toHaveBeenCalledOnce();
  });
});
