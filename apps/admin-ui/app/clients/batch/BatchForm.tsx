"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  CloudUpload,
  FileText,
  Loader2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { provisionBatchAction, type BatchResult } from "@/app/actions/provision";
import type { BatchResultRow } from "@/lib/api";

export function BatchForm() {
  const [state, action, pending] = useActionState<BatchResult | undefined, FormData>(provisionBatchAction, undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // Clear local file state on a successful submission so the next batch
  // doesn't accidentally reuse the previous selection.
  useEffect(() => {
    if (state?.ok) setFile(null);
  }, [state]);

  function pickFiles(files: FileList | null) {
    const f = files?.[0] ?? null;
    setFile(f);
    if (fileInputRef.current && files) fileInputRef.current.files = files;
  }

  return (
    <div className="space-y-5">
      <form action={action} className="space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            pickFiles(e.dataTransfer.files);
          }}
          className={`relative rounded-xl border-2 border-dashed transition-all
            ${dragOver ? "border-brand-500 bg-brand-50" : "border-ink-200 bg-ink-50/30 hover:bg-ink-50/60"}
            ${file ? "p-4" : "p-8"}`}
        >
          {!file ? (
            <label
              htmlFor="batch-file"
              className="flex flex-col items-center text-center cursor-pointer"
            >
              <div className="rounded-2xl bg-white border border-ink-200 p-3 shadow-soft text-brand-600">
                <CloudUpload className="h-6 w-6" />
              </div>
              <div className="mt-3 text-sm font-medium text-ink-900">
                Drop your CSV here, or <span className="text-brand-700">browse</span>
              </div>
              <div className="mt-1 text-xs text-ink-500">.csv up to 1 MB</div>
            </label>
          ) : (
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-white border border-ink-200 p-2 text-brand-600 shrink-0">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink-900 truncate">{file.name}</div>
                <div className="text-xs text-ink-500">{(file.size / 1024).toFixed(1)} KB</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="btn-icon"
                aria-label="Remove file"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            id="batch-file"
            type="file"
            name="file"
            accept=".csv,text/csv"
            required
            onChange={(e) => pickFiles(e.target.files)}
            className="absolute inset-0 opacity-0 cursor-pointer"
          />
        </div>

        {state && !state.ok && (
          <div role="alert" className="flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2.5 text-sm text-rose-700">
            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
            <span>{state.error}</span>
          </div>
        )}

        <div className="flex items-center justify-end">
          <button type="submit" disabled={pending || !file} className="btn-primary">
            {pending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Provisioning…
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Upload + provision
              </>
            )}
          </button>
        </div>
      </form>

      {state?.ok && <Results results={state.results} />}
    </div>
  );
}

function Results({ results }: { results: BatchResultRow[] }) {
  const ok = results.filter((r) => r.ok);
  const failed = results.filter((r) => !r.ok);
  const created = ok.filter((r) => r.ok && r.created).length;
  const updated = ok.length - created;

  return (
    <div className="animate-fade-in space-y-3">
      <div className="flex items-center justify-between border-t border-ink-100 pt-5">
        <h2 className="text-sm font-semibold text-ink-900">Results</h2>
        <div className="flex items-center gap-2 text-xs">
          {created > 0 && <span className="badge-success"><CheckCircle2 className="h-3 w-3" />{created} created</span>}
          {updated > 0 && <span className="badge-brand">{updated} updated</span>}
          {failed.length > 0 && <span className="badge-danger"><XCircle className="h-3 w-3" />{failed.length} failed</span>}
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-ink-500 text-[0.7rem] uppercase tracking-[0.06em]">
                <th className="text-left font-semibold px-4 py-3 w-16">Row</th>
                <th className="text-left font-semibold px-4 py-3 w-32">Status</th>
                <th className="text-left font-semibold px-4 py-3">Email</th>
                <th className="text-left font-semibold px-4 py-3">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {results.map((r) => (
                <tr key={r.row} className="hover:bg-ink-50/60 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-ink-500">#{r.row}</td>
                  <td className="px-4 py-3">
                    {r.ok ? (
                      r.created ? (
                        <span className="badge-success"><CheckCircle2 className="h-3 w-3" />Created</span>
                      ) : (
                        <span className="badge-brand">Updated</span>
                      )
                    ) : (
                      <span className="badge-danger"><XCircle className="h-3 w-3" />{r.step}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-700">{r.email ?? <span className="text-ink-400">—</span>}</td>
                  <td className="px-4 py-3">
                    {r.ok ? (
                      <Link
                        href={`/clients/${encodeURIComponent(r.slug)}`}
                        className="inline-flex items-center gap-1 text-brand-700 hover:text-brand-800 font-mono text-xs"
                      >
                        {r.record.booking_link}
                        <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    ) : (
                      <span className="text-rose-700 text-xs">{r.message}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
