"use client";

import { useState } from "react";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        } catch {
          /* noop — older browsers without clipboard API */
        }
      }}
      className="px-2 py-1 text-xs rounded border border-slate-300 bg-white hover:bg-slate-100"
    >
      {copied ? "Copied" : label}
    </button>
  );
}
