import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ME_KEY, useSession } from "../auth/session";
import { TextInput } from "../components/form";
import { Alert, Button } from "../components/ui";
import { errorMessage } from "../services/api";
import { auth } from "../services/endpoints";

export function TwoFactorSettings() {
  const { data: user } = useSession();
  const client = useQueryClient();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [enableCode, setEnableCode] = useState("");
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");

  const refreshMe = () => client.invalidateQueries({ queryKey: ME_KEY });

  const begin = useMutation({
    mutationFn: auth.twoFactorSetup,
    onSuccess: (data) => setSetup(data),
  });
  const enable = useMutation({
    mutationFn: () => auth.twoFactorEnable(enableCode),
    onSuccess: async () => {
      setSetup(null);
      setEnableCode("");
      await refreshMe();
    },
  });
  const disable = useMutation({
    mutationFn: () => auth.twoFactorDisable(disablePassword, disableCode),
    onSuccess: async () => {
      setDisablePassword("");
      setDisableCode("");
      await refreshMe();
    },
  });

  if (!user) return null;
  const enabled = Boolean(user.totp_enabled);

  return (
    <div className="space-y-4 text-sm">
      {enabled ? (
        <>
          <p className="text-slate-600">Authenticator app is required when you sign in.</p>
          <TextInput label="Password" type="password" value={disablePassword} onChange={setDisablePassword} autoComplete="current-password" />
          <TextInput label="Authenticator code" value={disableCode} onChange={setDisableCode} inputMode="numeric" autoComplete="one-time-code" />
          {disable.error ? <Alert kind="error">{errorMessage(disable.error)}</Alert> : null}
          <Button variant="secondary" loading={disable.isPending} onClick={() => disable.mutate()} disabled={!disablePassword || disableCode.length < 6}>
            Turn off two-factor
          </Button>
        </>
      ) : setup ? (
        <>
          <p className="text-slate-600">Add this secret to your authenticator app, then enter the 6-digit code.</p>
          <p className="break-all font-mono text-xs text-slate-800">{setup.secret}</p>
          <TextInput label="Verification code" value={enableCode} onChange={setEnableCode} inputMode="numeric" autoComplete="one-time-code" />
          {enable.error ? <Alert kind="error">{errorMessage(enable.error)}</Alert> : null}
          <div className="flex flex-wrap gap-2">
            <Button loading={enable.isPending} onClick={() => enable.mutate()} disabled={enableCode.length < 6}>
              Enable two-factor
            </Button>
            <Button variant="secondary" onClick={() => setSetup(null)}>Cancel</Button>
          </div>
        </>
      ) : (
        <>
          <p className="text-slate-600">Use an authenticator app (Google Authenticator, 1Password, etc.) for an extra sign-in step.</p>
          {begin.error ? <Alert kind="error">{errorMessage(begin.error)}</Alert> : null}
          <Button variant="secondary" loading={begin.isPending} onClick={() => begin.mutate()}>
            Set up authenticator
          </Button>
        </>
      )}
    </div>
  );
}
