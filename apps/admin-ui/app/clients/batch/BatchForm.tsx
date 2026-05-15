"use client";

import Link from "next/link";
import { useActionState } from "react";
import { provisionBatchAction, type BatchResult } from "@/app/actions/provision";

export function BatchForm() {
  const [state, action, pending] = useActionState<BatchResult | undefined, FormData>(provisionBatchAction, undefined);

  return (
    <div className="space-y-4">
      <form action={action} className="space-y-4">
        <input
          type="file"
          name="file"
          accept=".csv,text/csv"
          required
          className="block w-full text-sm text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded file:border file:border-slate-300 file:bg-white file:text-slate-700 hover:file:bg-slate-100"
        />
        {state && !state.ok && (
          <p className="text-sm text-red-600" role="alert">{state.error}</p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 hover:bg-slate-800"
        >
          {pending ? "Provisioning…" : "Upload + provision"}
        </button>
      </form>

      {state?.ok && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-2">Results</h2>
          <table className="w-full text-sm rounded border border-slate-200 overflow-hidden">
            <thead className="bg-slate-50 text-slate-600 uppercase text-xs tracking-wide">
              <tr>
                <th className="text-left px-3 py-2">Row</th>
                <th className="text-left px-3 py-2">Status</th>
                <th className="text-left px-3 py-2">Email</th>
                <th className="text-left px-3 py-2">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {state.results.map((r) => {
                if (r.ok) {
                  return (
                    <tr key={r.row} className="bg-white">
                      <td className="px-3 py-2 font-mono">{r.row}</td>
                      <td className="px-3 py-2">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
                          {r.created ? "created" : "updated"}
                        </span>
                      </td>
                      <td className="px-3 py-2">{r.email}</td>
                      <td className="px-3 py-2">
                        <Link href={`/clients/${encodeURIComponent(r.slug)}`} className="text-blue-700 underline">
                          {r.record.booking_link}
                        </Link>
                      </td>
                    </tr>
                  );
                }
                return (
                  <tr key={r.row} className="bg-white">
                    <td className="px-3 py-2 font-mono">{r.row}</td>
                    <td className="px-3 py-2">
                      <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                        failed @ {r.step}
                      </span>
                    </td>
                    <td className="px-3 py-2">{r.email ?? "—"}</td>
                    <td className="px-3 py-2 text-red-700">{r.message}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
