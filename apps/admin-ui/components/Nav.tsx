import Link from "next/link";
import { logoutAction } from "@/app/actions/auth";

export function Nav({ adminEmail }: { adminEmail: string | null }) {
  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-3 flex items-center justify-between">
        <Link href="/" className="font-semibold text-slate-900">glink admin</Link>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/" className="hover:underline text-slate-600">Clients</Link>
          <Link href="/clients/new" className="hover:underline text-slate-600">Add</Link>
          <Link href="/clients/batch" className="hover:underline text-slate-600">Batch</Link>
          {adminEmail && (
            <>
              <span className="text-slate-400">|</span>
              <span className="text-slate-500">{adminEmail}</span>
              <form action={logoutAction}>
                <button className="text-slate-600 hover:underline" type="submit">Sign out</button>
              </form>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
