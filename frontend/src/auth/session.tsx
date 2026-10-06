import { type QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Spinner } from "../components/ui";
import { ApiError } from "../services/api";
import { auth, preferences } from "../services/endpoints";
import type { User } from "../types";

export const ME_KEY = ["me"] as const;

export function useSession() {
  return useQuery<User | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await auth.me();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
}

const PUBLIC_QUERIES = new Set<unknown>([ME_KEY[0], "plans"]);

/** Forget everything cached for the previous user, without disturbing in-flight public queries. */
export function forgetUser(client: QueryClient): void {
  client.setQueryData(ME_KEY, null);
  client.removeQueries({ predicate: (q) => !PUBLIC_QUERIES.has(q.queryKey[0]) });
}

export function useSetSession() {
  const client = useQueryClient();
  return (user: User | null) => {
    if (user === null) forgetUser(client);
    else client.setQueryData(ME_KEY, user);
  };
}

/** Only allow same-site relative paths as post-login destinations (no open redirects). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : "/app";
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useSession();
  const location = useLocation();
  if (isLoading) return <Spinner />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useSession();
  if (isLoading) return <Spinner />;
  if (user) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

/** Until job preferences are saved, the app routes to the onboarding wizard. */
export function RequireOnboarded({ children }: { children: ReactNode }) {
  const { data, isLoading } = useQuery({ queryKey: ["preferences", "search"], queryFn: preferences.search });
  if (isLoading) return <Spinner />;
  if (data && !data.configured) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}
