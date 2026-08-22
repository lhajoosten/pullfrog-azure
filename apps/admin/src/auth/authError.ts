export type PublicAuthError =
  | "invalid_login_attempt"
  | "identity_provider_unavailable"
  | "identity_not_authorized"
  | "group_claim_overage"
  | "invalid_session"
  | "csrf_failed"
  | "unknown";

export function parseAuthError(search: string): PublicAuthError | null {
  const value = new URLSearchParams(search).get("auth_error");
  switch (value) {
    case null:
    case "invalid_login_attempt":
    case "identity_provider_unavailable":
    case "identity_not_authorized":
    case "group_claim_overage":
    case "invalid_session":
    case "csrf_failed":
      return value;
    default:
      return "unknown";
  }
}
