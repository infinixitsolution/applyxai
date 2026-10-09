import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, Spinner } from "../components/ui";
import { AuthShell, RegisterInstituteAside } from "../features/auth";
import { errorMessage } from "../services/api";
import { referrals } from "../services/endpoints";

export function ReferralPage() {
  const { code = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["referral", code, params.get("c")],
    queryFn: () => referrals.capture(code, params.get("c") || undefined),
    enabled: Boolean(code),
  });
  useEffect(() => {
    if (data?.referral_code) navigate(`/register/institute?r=${data.referral_code}`, { replace: true });
  }, [data, navigate]);
  return (
    <AuthShell
      asideTone="institute"
      brandTagline="Partner referral"
      kicker="Redirecting"
      title="Opening institute signup"
      aside={<RegisterInstituteAside />}
    >
      {isLoading ? (
        <Spinner label="Applying referral code…" />
      ) : error ? (
        <Alert kind="error">{errorMessage(error)}</Alert>
      ) : (
        <Spinner label="Taking you to registration…" />
      )}
    </AuthShell>
  );
}
