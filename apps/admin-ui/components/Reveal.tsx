"use client";

import { useState } from "react";
import { CopyButton } from "./CopyButton";

export function Reveal({ value, label = "Reveal" }: { value: string; label?: string }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <code className="px-2 py-1 rounded bg-slate-100 font-mono text-sm">
        {shown ? value : "•".repeat(Math.min(value.length, 24))}
      </code>
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        className="px-2 py-1 text-xs rounded border border-slate-300 bg-white hover:bg-slate-100"
      >
        {shown ? "Hide" : label}
      </button>
      <CopyButton value={value} />
    </div>
  );
}
