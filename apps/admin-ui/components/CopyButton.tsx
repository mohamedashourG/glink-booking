"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

type Variant = "default" | "ghost" | "primary";

export function CopyButton({
  value,
  label,
  variant = "default",
  className = "",
}: {
  value: string;
  label?: string;
  variant?: Variant;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  const base = {
    default: "btn btn-sm border border-ink-200 bg-white text-ink-700 px-2.5 hover:bg-ink-50 hover:border-ink-300 shadow-soft",
    ghost: "btn btn-sm text-ink-500 hover:bg-ink-100 hover:text-ink-900 px-2",
    primary: "btn btn-sm bg-brand-600 text-white px-3 hover:bg-brand-700",
  }[variant];

  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* clipboard API not available — silent */
        }
      }}
      aria-label={copied ? "Copied" : (label ?? "Copy")}
      className={`${base} ${copied ? "!text-emerald-700 !border-emerald-300 !bg-emerald-50" : ""} ${className}`}
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {label !== undefined && <span>{copied ? "Copied" : label}</span>}
    </button>
  );
}
