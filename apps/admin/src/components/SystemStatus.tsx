export type SystemStatusState = "loading" | "healthy" | "unavailable";

export interface SystemStatusProps {
  readonly state: SystemStatusState;
  readonly message: string;
}

export function SystemStatus({ state, message }: SystemStatusProps) {
  return (
    <section className="system-status" data-state={state} role="status">
      <span aria-hidden="true" className="system-status__indicator" />
      <span>{message}</span>
    </section>
  );
}
