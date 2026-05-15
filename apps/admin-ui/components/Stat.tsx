import type { LucideIcon } from "lucide-react";

export function Stat({
  label,
  value,
  Icon,
  tone = "default",
  hint,
}: {
  label: string;
  value: string | number;
  Icon: LucideIcon;
  tone?: "default" | "success" | "warn" | "danger" | "brand";
  hint?: string;
}) {
  const toneCls = {
    default: "bg-ink-100 text-ink-600",
    success: "bg-emerald-100 text-emerald-700",
    warn: "bg-amber-100 text-amber-700",
    danger: "bg-rose-100 text-rose-700",
    brand: "bg-brand-100 text-brand-700",
  }[tone];

  return (
    <div className="card card-pad flex items-start justify-between">
      <div className="min-w-0">
        <div className="text-sm text-ink-500">{label}</div>
        <div className="mt-1.5 text-2xl font-semibold text-ink-900 tabular-nums">{value}</div>
        {hint && <div className="mt-1 text-xs text-ink-500">{hint}</div>}
      </div>
      <div className={`rounded-xl p-2.5 ${toneCls}`}>
        <Icon className="h-5 w-5" />
      </div>
    </div>
  );
}
