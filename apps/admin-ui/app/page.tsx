import Link from "next/link";
import { adminApi } from "@/lib/api";
import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { CopyButton } from "@/components/CopyButton";

const COVERAGE_BADGE: Record<string, string> = {
  platform: "bg-emerald-100 text-emerald-800",
  "per-user": "bg-amber-100 text-amber-800",
  none: "bg-red-100 text-red-800",
};

export default async function Dashboard() {
  const { token, email } = await requireToken();
  const { clients } = await adminApi.listClients(token);

  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Clients</h1>
            <p className="text-sm text-slate-500 mt-1">{clients.length} provisioned.</p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/clients/batch"
              className="px-3 py-2 text-sm rounded border border-slate-300 bg-white hover:bg-slate-100"
            >
              Batch provision
            </Link>
            <Link
              href="/clients/new"
              className="px-3 py-2 text-sm rounded bg-slate-900 text-white hover:bg-slate-800"
            >
              + Add client
            </Link>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600 uppercase text-xs tracking-wide">
              <tr>
                <th className="text-left px-4 py-3">Slug</th>
                <th className="text-left px-4 py-3">Name</th>
                <th className="text-left px-4 py-3">Email</th>
                <th className="text-left px-4 py-3">Booking link</th>
                <th className="text-left px-4 py-3">Webhook</th>
                <th className="text-right px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {clients.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-400">
                    No clients yet. Use <Link href="/clients/new" className="underline">Add client</Link>.
                  </td>
                </tr>
              )}
              {clients.map((c) => {
                const bookingLink = `${process.env.CAL_PUBLIC_BASE || "http://localhost:3000"}/${c.slug}/30min`;
                return (
                  <tr key={c.email} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-slate-900">{c.slug}</td>
                    <td className="px-4 py-3 text-slate-700">{c.full_name}</td>
                    <td className="px-4 py-3 text-slate-500">{c.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <a href={bookingLink} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">
                          {c.slug}/30min
                        </a>
                        <CopyButton value={bookingLink} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${COVERAGE_BADGE[c.webhook_coverage] ?? "bg-slate-100 text-slate-700"}`}>
                        {c.webhook_coverage}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/clients/${encodeURIComponent(c.slug)}`} className="text-slate-700 hover:underline">
                        View →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}
