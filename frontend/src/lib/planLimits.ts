export const RESUMES_UNLIMITED = 999_999;
export const MOCK_INTERVIEWS_UNLIMITED = 999_999;

export function formatResumeLimit(limit: number): string {
  return limit >= RESUMES_UNLIMITED ? "Unlimited" : limit.toLocaleString();
}

export function formatMockInterviewLimit(limit: number): string {
  return limit >= MOCK_INTERVIEWS_UNLIMITED ? "Unlimited" : limit.toLocaleString();
}
