import { requireToken } from "@/lib/server-session";
import { Nav } from "@/components/Nav";
import { NewClientForm } from "./NewClientForm";

export default async function NewClientPage() {
  const { email } = await requireToken();
  return (
    <>
      <Nav adminEmail={email} />
      <main className="mx-auto max-w-2xl px-6 py-8">
        <h1 className="text-2xl font-semibold text-slate-900">Add client</h1>
        <p className="text-sm text-slate-500 mt-1">
          Provisions a new cal.diy login + 30-minute event type with the standard policy.
        </p>
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
          <NewClientForm />
        </div>
      </main>
    </>
  );
}
