import { useQuery } from "@tanstack/react-query";
import { site } from "../services/endpoints";

export function usePublicSite() {
  return useQuery({
    queryKey: ["site", "public"],
    queryFn: site.public,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
