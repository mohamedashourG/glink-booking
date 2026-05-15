import Link from "next/link";
import { ArrowLeft, FileSpreadsheet } from "lucide-react";
import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { BatchForm } from "./BatchForm";

export default async function BatchPage() {
  const { email } = await requireToken();
  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-4xl px-6 py-8 animate-fade-in">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          All clients
        </Link>

        <div className="mt-4">
          <h1 className="text-[1.65rem] font-semibold text-ink-900 tracking-tight">Batch provision</h1>
          <p className="mt-1 text-sm text-ink-500">
            Upload a CSV. We&apos;ll create or update one client per row and report back inline.
          </p>
        </div>

        <div className="mt-6 card card-pad bg-ink-50/40 border-dashed">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-white text-brand-600 p-2 border border-ink-200">
              <FileSpreadsheet className="h-4 w-4" />
            </div>
            <div className="text-sm text-ink-700">
              <div className="font-medium text-ink-900">CSV format</div>
              <div className="mt-1.5">
                <span className="text-ink-500">Required:</span>{" "}
                <code className="chip-mono">full_name</code>{" "}
                <code className="chip-mono">email</code>{" "}
                <code className="chip-mono">slug</code>
              </div>
              <div className="mt-1.5">
                <span className="text-ink-500">Optional:</span>{" "}
                <code className="chip-mono">timezone</code>{" "}
                <code className="chip-mono">work_start</code>{" "}
                <code className="chip-mono">work_end</code>{" "}
                <code className="chip-mono">calendly_url</code>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 card card-pad">
          <BatchForm />
        </div>
      </main>
    </>
  );
}
