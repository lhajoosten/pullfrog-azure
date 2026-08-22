import type { PublicAuthError } from "../auth/authError";

export interface AuthenticationErrorPanelProps {
  readonly error: PublicAuthError;
}

function errorMessage(error: PublicAuthError): string {
  switch (error) {
    case "identity_not_authorized":
      return "This Microsoft account is not authorized.";
    case "group_claim_overage":
      return "Group membership could not be verified. Ask an administrator to authorize your account directly.";
    case "identity_provider_unavailable":
      return "Microsoft sign-in is temporarily unavailable. Please try again.";
    case "invalid_login_attempt":
    case "invalid_session":
    case "csrf_failed":
    case "unknown":
      return "Microsoft sign-in failed. Please try again.";
  }
}

export function AuthenticationErrorPanel({
  error,
}: AuthenticationErrorPanelProps) {
  return (
    <section className="authentication-error" role="alert">
      <strong>Sign-in failed</strong>
      <span>{errorMessage(error)}</span>
    </section>
  );
}
