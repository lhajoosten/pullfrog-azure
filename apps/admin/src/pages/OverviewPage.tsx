import { useAdminSession } from "../api/useAdminSession";
import { useLiveness } from "../api/useLiveness";
import { useLogout } from "../api/useLogout";
import { parseAuthError } from "../auth/authError";
import { AdminSessionPanel } from "../components/AdminSessionPanel";
import { AuthenticationErrorPanel } from "../components/AuthenticationErrorPanel";
import { SignInPanel } from "../components/SignInPanel";
import { SystemStatus } from "../components/SystemStatus";

function AuthenticatedOverview({
  displayName,
}: {
  displayName: string | null;
}) {
  const liveness = useLiveness();
  const logout = useLogout();

  let status = (
    <SystemStatus state="healthy" message="Control plane is reachable" />
  );

  if (liveness.isPending) {
    status = <SystemStatus state="loading" message="Checking control plane" />;
  } else if (liveness.isError) {
    status = (
      <SystemStatus
        state="unavailable"
        message="Control plane is unavailable"
      />
    );
  }

  return (
    <div className="overview-stack">
      <AdminSessionPanel
        displayName={displayName}
        isLogoutPending={logout.isPending}
        onLogout={() => logout.mutate()}
      />
      {status}
    </div>
  );
}

export default function OverviewPage() {
  const session = useAdminSession();

  if (session.isPending) {
    return (
      <SystemStatus state="loading" message="Checking administrator session" />
    );
  }
  if (session.isError || session.data === undefined) {
    return (
      <SystemStatus
        state="unavailable"
        message="Administrator session is unavailable"
      />
    );
  }
  if (session.data === null) {
    const authError = parseAuthError(window.location.search);
    return (
      <div className="overview-stack">
        {authError === null ? null : (
          <AuthenticationErrorPanel error={authError} />
        )}
        <SignInPanel />
      </div>
    );
  }
  return <AuthenticatedOverview displayName={session.data.display_name} />;
}
