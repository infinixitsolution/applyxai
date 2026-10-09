import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { rememberNext, useSession } from "../auth/session";
import { Alert, Button, ButtonLink, Spinner } from "../components/ui";
import { AuthShell, InviteAside } from "../features/auth";
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
  useEffect(() => {
    if (token) rememberNext(`/invite/${token}`);
  }, [token]);
  return (
    <AuthShell
      asideTone="institute"
      brandTagline="Campus invitation"
      kicker="Institute invite"
      title="You're invited"
      subtitle={data?.institute_name ? <>Join <strong>{data.institute_name}</strong> on ApplyXAI</> : undefined}
      aside={<InviteAside instituteName={data?.institute_name} />}
    >
      {isLoading ? (
        <Spinner label="Loading invitation…" />
      ) : error ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : accept.isSuccess ? (
        <Alert kind="success">Seat accepted. You can use ApplyXAI with your campus plan.</Alert>
      ) : (
        <div className="auth-flow">
          <p className="auth-flow-lead">
            This invitation was sent to <strong>{data?.email}</strong>. Sign in or register with that address to accept.
          </p>
          {!user ? (
            <div className="auth-stack-buttons">
              <ButtonLink to={`/register?next=/invite/${token}`} className="auth-primary w-full">
                Create an account
              </ButtonLink>
              <ButtonLink to={`/login?next=/invite/${token}`} variant="secondary" className="auth-secondary w-full">
                Log in to accept
              </ButtonLink>
            </div>
          ) : (
            <Button className="auth-primary w-full" onClick={() => accept.mutate()} loading={accept.isPending}>
              Accept invitation
            </Button>
          )}
          {accept.error && <Alert kind="error">{errorMessage(accept.error)}</Alert>}
          <p className="auth-flow-foot">
            <Link to="/" className="auth-text-link">
              Back home
            </Link>
          </p>
        </div>
      )}
    </AuthShell>
  );
}
