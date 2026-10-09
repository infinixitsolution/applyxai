import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, Spinner } from "../components/ui";
import { AuthCard } from "../layouts/PublicLayout";
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
    <AuthCard title="Partner referral">
      {isLoading ? <Spinner label="Opening signup…" /> : error ? <Alert kind="error">{errorMessage(error)}</Alert> : <Spinner />}
    </AuthCard>
  );
}
