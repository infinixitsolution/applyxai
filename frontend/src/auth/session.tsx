import { type QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Alert, Spinner } from "../components/ui";
import { ApiError, errorMessage } from "../services/api";
import { auth, preferences } from "../services/endpoints";
import { resetCandidateWelcomeForLogin } from "../lib/candidateWelcome";
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
    else {
      resetCandidateWelcomeForLogin(user.id);
      client.setQueryData(ME_KEY, user);
    }
  };
}

const NEXT_STORAGE = "applyxai.next";

function isSafeNext(next: string | null): next is string {
  return Boolean(next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\"));
}

/** Only allow same-site relative paths as post-login destinations (no open redirects). */
export function safeNext(next: string | null, fallback = "/app"): string {
  return isSafeNext(next) ? next : fallback;
}

/** Keep `next` across register → verify email → login (query strings get dropped on the email link). */
export function rememberNext(next: string | null): void {
  if (typeof sessionStorage === "undefined") return;
  if (isSafeNext(next)) sessionStorage.setItem(NEXT_STORAGE, next);
}

export function storedNext(): string | null {
  if (typeof sessionStorage === "undefined") return null;
  return sessionStorage.getItem(NEXT_STORAGE);
}

export function consumeNext(): string | null {
  const value = storedNext();
  if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(NEXT_STORAGE);
  return value;
}

/** Append a safe `next` query to a path that may already have search params. */
export function withNext(path: string, next: string | null): string {
  if (!isSafeNext(next)) return path;
  return `${path}${path.includes("?") ? "&" : "?"}next=${encodeURIComponent(next)}`;
}

/** Where a signed-in user lands by default. */
export function homeFor(user: User): string {
  if (user.is_admin) return "/admin";
  if (user.workspace === "institute") return "/institute";
  if (user.workspace === "partner") return "/partner";
  return "/app";
}

function SessionGate({ children, pending }: { children: ReactNode; pending: boolean }) {
  const { isError, error } = useSession();
  if (pending) return <Spinner />;
  if (isError) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16">
        <Alert kind="error">{errorMessage(error)}</Alert>
        <p className="mt-3 text-sm text-slate-600">
          Start the API from the project root:{" "}
          <code className="rounded bg-slate-100 px-1">python -m uvicorn backend.app.main:app --reload --port 8000</code>
        </p>
      </div>
    );
  }
  return <>{children}</>;
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending, isError } = useSession();
  const location = useLocation();
  if (isPending || isError) return <SessionGate pending={isPending}>{null}</SessionGate>;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return <>{children}</>;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useSession();
  if (isLoading) return <Spinner />;
  if (user) return <Navigate to={homeFor(user)} replace />;
  return <>{children}</>;
}

/** Admin pages. The API enforces this too; the guard only keeps non-admins out of a broken UI. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { data: user, isPending, isError } = useSession();
  if (isPending || isError) return <SessionGate pending={isPending}>{null}</SessionGate>;
  if (!user?.is_admin) return <Navigate to={user ? homeFor(user) : "/login"} replace />;
  return <>{children}</>;
}

export function RequireInstitute({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useSession();
  if (isLoading) return <Spinner />;
  if (user?.workspace !== "institute") return <Navigate to={user ? homeFor(user) : "/login"} replace />;
  return <>{children}</>;
}

export function RequirePartner({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useSession();
  if (isLoading) return <Spinner />;
  if (user?.workspace !== "partner") return <Navigate to={user ? homeFor(user) : "/login"} replace />;
  return <>{children}</>;
}

/** Until job preferences are saved, the app routes to the onboarding wizard. */
export function RequireOnboarded({ children }: { children: ReactNode }) {
  const { data: user } = useSession();
  const { data, isLoading } = useQuery({ queryKey: ["preferences", "search"], queryFn: preferences.search });
  if (user && user.workspace && user.workspace !== "app") return <Navigate to={homeFor(user)} replace />;
  if (isLoading) return <Spinner />;
  if (data && !data.configured) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}
