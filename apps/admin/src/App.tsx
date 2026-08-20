import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import OverviewPage from "./pages/OverviewPage";
import "./styles/tokens.css";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <main>
        <h1>Pullfrog Azure</h1>
        <OverviewPage />
      </main>
    </QueryClientProvider>
  );
}
