"use client";

import { useEffect, useRef, useState } from "react";
import { LogOut, ShieldCheck } from "lucide-react";
import { Avatar } from "./Avatar";
import { Tooltip } from "./Tooltip";
import { logoutAction } from "@/app/actions/auth";

export function SidebarUserMenu({ email }: { email: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!ref.current || ref.current.contains(e.target as Node)) return;
      setOpen(false);
    }
    function onEsc(e: KeyboardEvent) { if (e.key === "Escape") setOpen(false); }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  return (
    <div className="relative" ref={ref}>
      {open ? null : (
        <Tooltip label={email}>
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-haspopup="menu"
            aria-expanded={false}
            className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-ink-100 transition-colors"
          >
            <Avatar seed={email} size="sm" />
          </button>
        </Tooltip>
      )}
      {open && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          aria-haspopup="menu"
          aria-expanded={true}
          className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-ink-100 transition-colors"
        >
          <Avatar seed={email} size="sm" />
        </button>
      )}
      {open && (
        <div
          role="menu"
          className="absolute bottom-0 left-full ml-2 w-64 origin-bottom-left rounded-xl border border-ink-200 bg-white shadow-pop overflow-hidden animate-scale-in z-50"
        >
          <div className="p-3 border-b border-ink-100 flex items-center gap-3">
            <Avatar seed={email} size="md" />
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink-900 truncate">{email}</div>
              <div className="text-xs text-ink-500 inline-flex items-center gap-1 mt-0.5">
                <ShieldCheck className="h-3 w-3 text-emerald-600" /> Admin
              </div>
            </div>
          </div>
          <form action={logoutAction}>
            <button
              type="submit"
              className="flex w-full items-center gap-2 px-3 py-2.5 text-sm text-ink-700 hover:bg-ink-50"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
