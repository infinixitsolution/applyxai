import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useToast } from "./Toast";
import { TextInput } from "./form";
import { Button, Card, Spinner } from "./ui";
import { desktopAgent, isDesktop } from "../lib/desktop";
import { errorMessage } from "../services/api";

/** Saved on this PC for LinkedIn and Naukri auto-login (ApplyXAI Desktop). */
export function AgentCredentialsPanel({ className }: { className?: string }) {
  const toast = useToast();
  const client = useQueryClient();
  const agent = desktopAgent();

  const loaded = useQuery({
    queryKey: ["desktop-agent-credentials"],
    queryFn: () => agent!.readCredentials(),
    enabled: isDesktop && Boolean(agent),
  });

  const [linkedinEmail, setLinkedinEmail] = useState("");
  const [linkedinPassword, setLinkedinPassword] = useState("");
  const [naukriEmail, setNaukriEmail] = useState("");
  const [naukriPassword, setNaukriPassword] = useState("");

  useEffect(() => {
    if (!loaded.data) return;
    setLinkedinEmail(loaded.data.username);
    setLinkedinPassword(loaded.data.password);
    setNaukriEmail(loaded.data.naukri_username);
    setNaukriPassword(loaded.data.naukri_password);
  }, [loaded.data]);

  const save = useMutation({
    mutationFn: () =>
      agent!.saveCredentials({
        username: linkedinEmail,
        password: linkedinPassword,
        naukri_username: naukriEmail,
        naukri_password: naukriPassword,
      }),
    onSuccess: () => {
      toast.success("Login credentials saved on this computer.");
      void client.invalidateQueries({ queryKey: ["desktop-agent-credentials"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!isDesktop || !agent) return null;

  return (
    <Card className={className}>
      <p className="text-sm font-medium text-slate-900">Job site logins (this computer)</p>
      <p className="mt-1 text-xs text-slate-600">
        Passwords stay on this device and are never sent to ApplyXAI. During a run, automation opens a separate Chrome
        profile and signs in with these credentials when provided. Leave a site blank to sign in by hand in that window.
      </p>
      {loaded.isLoading ? (
        <Spinner label="Loading saved logins\u2026" />
      ) : (
        <div className="mt-4 space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">LinkedIn</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <TextInput
                label="Email"
                type="email"
                autoComplete="username"
                value={linkedinEmail}
                onChange={setLinkedinEmail}
              />
              <TextInput
                label="Password"
                type="password"
                autoComplete="current-password"
                value={linkedinPassword}
                onChange={setLinkedinPassword}
              />
            </div>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Naukri</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <TextInput
                label="Email"
                type="email"
                autoComplete="username"
                value={naukriEmail}
                onChange={setNaukriEmail}
              />
              <TextInput
                label="Password"
                type="password"
                autoComplete="current-password"
                value={naukriPassword}
                onChange={setNaukriPassword}
              />
            </div>
          </div>
          <Button size="sm" loading={save.isPending} onClick={() => save.mutate()}>
            Save credentials
          </Button>
        </div>
      )}
    </Card>
  );
}
