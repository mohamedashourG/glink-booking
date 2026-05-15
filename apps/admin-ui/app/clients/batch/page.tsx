import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { BatchForm } from "./BatchForm";

export default async function BatchPage() {
  const { email } = await requireToken();
  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-3xl px-6 py-8">
        <h1 className="text-2xl font-semibold text-slate-900">Batch provision</h1>
        <p className="text-sm text-slate-500 mt-1">
          CSV with header row. Required columns: <code className="font-mono">full_name, email, slug</code>.
          Optional: <code className="font-mono">timezone, work_start, work_end, calendly_url</code>.
        </p>
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
          <BatchForm />
        </div>
      </main>
    </>
  );
}
