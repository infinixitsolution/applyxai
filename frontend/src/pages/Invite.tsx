import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { rememberNext, useSession } from "../auth/session";
import { Alert, Button, ButtonLink, Spinner } from "../components/ui";
import { AuthCard } from "../layouts/PublicLayout";
import { errorMessage } from "../services/api";
import { invites } from "../services/endpoints";

export function InvitePage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const { data: user } = useSession();
  const { data, isLoading, error } = useQuery({
    queryKey: ["invite", token],
    queryFn: () => invites.preview(token),
    enabled: Boolean(token),
  });
  const accept = useMutation({
    mutationFn: () => invites.accept(token),
    onSuccess: () => navigate("/app", { replace: true }),
  });
  useEffect(() => { if (token) rememberNext(`/invite/${token}`); }, [token]);
  return (
    <AuthCard title="Campus invitation" subtitle={data?.institute_name}>
      {isLoading ? <Spinner /> : error ? <Alert kind="error">{errorMessage(error)}</Alert> : accept.isSuccess ? (
        <Alert kind="success">Seat accepted. You can use ApplyXAI with your campus plan.</Alert>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">This invitation was sent to <strong>{data?.email}</strong>.</p>
          {!user ? (
            <div className="space-y-2">
              <ButtonLink to={`/register?next=/invite/${token}`} className="w-full">Create an account</ButtonLink>
              <ButtonLink to={`/login?next=/invite/${token}`} variant="secondary" className="w-full">Log in to accept</ButtonLink>
            </div>
          ) : (
            <Button className="w-full" onClick={() => accept.mutate()} loading={accept.isPending}>Accept invitation</Button>
          )}
          {accept.error && <Alert kind="error">{errorMessage(accept.error)}</Alert>}
          <p className="text-center text-xs text-slate-500"><Link to="/" className="underline">Back home</Link></p>
        </div>
      )}
    </AuthCard>
  );
}
