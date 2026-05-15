"use client";

import { type ReactNode, useState } from "react";

// Tiny CSS-only tooltip for the icon-only sidebar. Appears on hover/focus,
// no portal — sits absolutely positioned to the right of the trigger so it
// floats over neighbouring chrome.
export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <div
          role="tooltip"
          className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-brand-700 px-2 py-1 text-xs font-medium text-white shadow-pop animate-fade-in"
        >
          {label}
          <span className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-brand-700" />
        </div>
      )}
    </div>
  );
}
