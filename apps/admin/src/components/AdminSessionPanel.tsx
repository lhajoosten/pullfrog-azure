export interface AdminSessionPanelProps {
  readonly displayName: string | null;
  readonly isLogoutPending: boolean;
  readonly onLogout: () => void;
}

export function AdminSessionPanel({
  displayName,
  isLogoutPending,
  onLogout,
}: AdminSessionPanelProps) {
  return (
    <section className="admin-session" aria-label="Administrator session">
      <span>
        {displayName === null ? "Signed in" : `Signed in as ${displayName}`}
      </span>
      <button type="button" disabled={isLogoutPending} onClick={onLogout}>
        {isLogoutPending ? "Signing out" : "Sign out"}
      </button>
    </section>
  );
}
