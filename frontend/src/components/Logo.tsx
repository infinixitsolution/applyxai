import { Link } from "react-router-dom";

const MASCOT = "/mascot.png";

export function Logo({ to = "/", size = "md" }: { to?: string; size?: "sm" | "md" | "lg" }) {
  const img = size === "sm" ? "h-7 w-7" : size === "lg" ? "h-12 w-12" : "h-9 w-9";
  const text = size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-lg";
  return (
    <Link to={to} className="flex items-center gap-2.5 font-semibold text-slate-900">
      <img src={MASCOT} alt="" className={`${img} rounded-xl object-cover shadow-sm ring-1 ring-slate-200/80`} width={48} height={48} />
      <span className={`${text} tracking-tight`}>
        Apply<span className="text-brand-600">XAI</span>
      </span>
    </Link>
  );
}
