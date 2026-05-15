"use client";

import { useActionState } from "react";
import { Mail, Lock, Loader2, ArrowRight, AlertTriangle } from "lucide-react";
import { loginAction, type LoginActionResult } from "@/app/actions/auth";

export function LoginForm({ next }: { next: string }) {
  const [state, formAction, pending] = useActionState<LoginActionResult, FormData>(loginAction, undefined);
  return (
    <form action={formAction} className="space-y-4">
      <input type="hidden" name="next" value={next} />

      <div>
        <label htmlFor="email" className="label">Email</label>
        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400 pointer-events-none" />
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="you@agency.com"
            required
            className="input input-with-icon"
          />
        </div>
      </div>

      <div>
        <label htmlFor="password" className="label">Password</label>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-400 pointer-events-none" />
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            required
            className="input input-with-icon"
          />
        </div>
      </div>

      {state?.error && (
        <div role="alert" className="flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2.5 text-sm text-rose-700">
          <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{state.error}</span>
        </div>
      )}

      <button type="submit" disabled={pending} className="btn-primary w-full py-2.5">
        {pending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Signing in…
          </>
        ) : (
          <>
            Sign in
            <ArrowRight className="h-4 w-4" />
          </>
        )}
      </button>
    </form>
  );
}
