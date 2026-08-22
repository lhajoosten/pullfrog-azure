export function SignInPanel() {
  return (
    <section className="admin-panel" aria-labelledby="sign-in-title">
      <h2 id="sign-in-title">Administrator access</h2>
      <p>
        Use an authorized account from the configured Microsoft Entra tenant.
      </p>
      <a className="admin-action" href="/api/v1/auth/login?return_to=%2F">
        Sign in with Microsoft
      </a>
    </section>
  );
}
