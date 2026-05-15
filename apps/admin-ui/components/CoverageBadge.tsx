import { CheckCircle2, AlertCircle, XCircle } from "lucide-react";

type Coverage = "platform" | "per-user" | "none";

const SPEC: Record<Coverage, { cls: string; Icon: typeof CheckCircle2; label: string }> = {
  platform: { cls: "badge-success", Icon: CheckCircle2, label: "Platform" },
  "per-user": { cls: "badge-warn", Icon: AlertCircle, label: "Per-user" },
  none: { cls: "badge-danger", Icon: XCircle, label: "None" },
};

export function CoverageBadge({ value }: { value: string }) {
  const spec = SPEC[value as Coverage] ?? { cls: "badge-neutral", Icon: AlertCircle, label: value };
  const { Icon } = spec;
  return (
    <span className={spec.cls}>
      <Icon className="h-3 w-3" />
      {spec.label}
    </span>
  );
}
