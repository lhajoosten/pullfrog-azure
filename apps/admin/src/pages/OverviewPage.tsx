import { useLiveness } from "../api/useLiveness";
import { SystemStatus } from "../components/SystemStatus";

export default function OverviewPage() {
  const liveness = useLiveness();

  if (liveness.isPending) {
    return <SystemStatus state="loading" message="Checking control plane" />;
  }
  if (liveness.isError) {
    return (
      <SystemStatus
        state="unavailable"
        message="Control plane is unavailable"
      />
    );
  }
  return <SystemStatus state="healthy" message="Control plane is reachable" />;
}
