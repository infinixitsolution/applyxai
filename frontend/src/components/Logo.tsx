import { Link } from "react-router-dom";

export function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 font-semibold text-slate-900">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="8" className="fill-brand-600" />
        <path d="M9 23 16 8l7 15h-4l-3-7-3 7z" fill="#fff" />
      </svg>
      <span className="text-lg tracking-tight">Apply<span className="text-brand-600">XAI</span></span>
    </Link>
  );
}
