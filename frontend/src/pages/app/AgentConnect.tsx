import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Button, Card, PageHeader } from "../../components/ui";
import { errorMessage } from "../../services/api";
import { automation } from "../../services/endpoints";

type Phase = "idle" | "approving" | "done" | "error";

export function AgentConnectPage() {
  const [params] = useSearchParams();
  const session = params.get("session")?.trim() ?? "";
  const [phase, setPhase] = useState<Phase>("idle");
  const [detail, setDetail] = useState("");

  const approve = useMutation({
    mutationFn: () => automation.approveConnect(session),
    onSuccess: () => {
      setPhase("done");
      setDetail("This computer is connected. You can close this tab and return to the desktop app.");
    },
    onError: (e) => {
      setPhase("error");
      setDetail(errorMessage(e));
    },
  });

  const invalid = useMemo(() => !session || !/^[0-9a-f-]{36}$/i.test(session), [session]);

  useEffect(() => {
    if (invalid) return;
    setPhase("approving");
    approve.mutate();
  }, [invalid, session]);

  return (
    <>
      <PageHeader title="Connect desktop agent" description="Approve this computer for automation runs." />
      <Card className="max-w-lg">
        {invalid ? (
          <Alert kind="error">Missing or invalid connect link. Use Connect — Local or Connect — Live in the desktop app.</Alert>
        ) : phase === "approving" || approve.isPending ? (
          <div className="flex items-center gap-3 text-slate-700">
            <Loader2 className="h-5 w-5 animate-spin text-brand-600" aria-hidden />
            <span>Connecting this computer to your account…</span>
          </div>
        ) : phase === "done" ? (
          <div className="space-y-3">
            <p className="flex items-center gap-2 font-medium text-green-700">
              <CheckCircle2 className="h-5 w-5" aria-hidden /> Connected
            </p>
            <p className="text-sm text-slate-600">{detail}</p>
            <ButtonLink to="/app/automation" />
          </div>
        ) : (
          <div className="space-y-3">
            <p className="flex items-center gap-2 font-medium text-red-700">
              <XCircle className="h-5 w-5" aria-hidden /> Could not connect
            </p>
            <Alert kind="error">{detail}</Alert>
            <Button onClick={() => { setPhase("idle"); approve.mutate(); }} loading={approve.isPending}>
              Try again
            </Button>
          </div>
        )}
      </Card>
    </>
  );
}

function ButtonLink({ to }: { to: string }) {
  return (
    <Link to={to} className="inline-flex text-sm font-medium text-brand-600 hover:underline">
      Open Automation
    </Link>
  );
}
