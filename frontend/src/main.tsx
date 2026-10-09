import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { forgetUser, ME_KEY } from "./auth/session";
import { ToastProvider } from "./components/Toast";
import "./index.css";
import "./styles/home.css";
import "./styles/landing-hero.css";
import "./styles/login-page.css";
import "./styles/responsive.css";
import { ApiError, onSessionExpired } from "./services/api";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Don't retry client errors (401/403/404/422); retry transient server/network failures twice.
      retry: (count, error) => !(error instanceof ApiError && error.status > 0 && error.status < 500) && count < 2,
    },
  },
});

// A signed-in session that can no longer be refreshed: forget the user's data; the route guards
// then redirect to /login. Anonymous visitors (no user cached) are left alone.
onSessionExpired(() => {
  if (queryClient.getQueryData(ME_KEY)) forgetUser(queryClient);
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
