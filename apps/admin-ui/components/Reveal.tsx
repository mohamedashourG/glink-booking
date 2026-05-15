"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { CopyButton } from "./CopyButton";

export function Reveal({ value }: { value: string }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <code
        className={`flex-1 font-mono text-sm rounded-lg bg-ink-100 px-3 py-2 tracking-tight transition-colors
          ${shown ? "text-ink-900" : "text-ink-400 select-none"}`}
      >
        {shown ? value : "•".repeat(Math.min(value.length, 24))}
      </code>
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? "Hide password" : "Reveal password"}
        className="btn btn-sm border border-ink-200 bg-white text-ink-700 px-2.5 hover:bg-ink-50 hover:border-ink-300 shadow-soft"
      >
        {shown ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        {shown ? "Hide" : "Reveal"}
      </button>
      <CopyButton value={value} />
    </div>
  );
}
